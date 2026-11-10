#!/usr/bin/env python3
"""Public reverse proxy in front of the loopback VoiceStudio API.

The API treats every loopback peer as an administrator and ignores
OMNIVOICE_API_KEY for that peer. A proxy on this machine is a loopback peer,
so it must tell Uvicorn who the real client was. Uvicorn trusts
X-Forwarded-For only from 127.0.0.1 (its default). This process:

* drops any forwarding headers the client sent (a forged
  ``X-Forwarded-For: 127.0.0.1`` would otherwise look like loopback);
* sets one X-Forwarded-For from the accepted socket;
* leaves Host unchanged so the browser origin and the API origin match.

WebSocket upgrades are spliced through. Ordinary HTTP requests are marked
``Connection: close`` so a later request on the same socket cannot skip the
header rewrite.
"""

from __future__ import annotations

import asyncio
import os
import sys

_DROP = {
    "x-forwarded-for",
    "x-forwarded-proto",
    "x-forwarded-host",
    "x-real-ip",
    "forwarded",
    "keep-alive",
    "proxy-connection",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "connection",
    "upgrade",
}

_MAX_HEAD = 64 * 1024


def rewrite_request(raw_head: bytes, peer_ip: str, proto: str = "http") -> bytes:
    """Return request headers safe to send to the loopback API."""
    if not peer_ip or any(ch.isspace() for ch in peer_ip):
        raise ValueError("peer address must be a single token")
    lines = raw_head.decode("iso-8859-1").split("\r\n")
    if not lines or " " not in lines[0]:
        raise ValueError("not an HTTP request")
    kept: list[str] = []
    host = ""
    upgrade = ""
    connection_upgrade = False
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        key = name.strip().lower()
        val = value.strip()
        if key == "host":
            host = val
        if key == "upgrade":
            upgrade = val
        if key == "connection" and "upgrade" in val.lower():
            connection_upgrade = True
        if key in _DROP:
            continue
        kept.append(f"{name.strip()}: {val}")
    websocket = connection_upgrade and upgrade.lower() == "websocket"
    if websocket:
        kept.append("Connection: Upgrade")
        kept.append(f"Upgrade: {upgrade}")
    else:
        kept.append("Connection: close")
    kept.append(f"X-Forwarded-For: {peer_ip}")
    kept.append(f"X-Forwarded-Proto: {proto}")
    if host:
        kept.append(f"X-Forwarded-Host: {host}")
    body = lines[0] + "\r\n" + "\r\n".join(kept) + "\r\n"
    return body.encode("iso-8859-1")


async def _pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await src.read(65536)
            if not chunk:
                break
            dst.write(chunk)
            await dst.drain()
    except (ConnectionError, asyncio.IncompleteReadError, BrokenPipeError):
        pass
    try:
        dst.close()
    except Exception:
        pass


async def _read_head(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = await reader.read(4096)
        if not chunk:
            raise ConnectionError("client closed before sending headers")
        data += chunk
        if len(data) > _MAX_HEAD:
            raise ValueError("request headers are too large")
    head, rest = data.split(b"\r\n\r\n", 1)
    return head, rest


def _peer_ip(writer: asyncio.StreamWriter) -> str:
    peer = writer.get_extra_info("peername")
    if not peer:
        return "0.0.0.0"
    host = peer[0]
    # IPv4-mapped IPv6 (::ffff:1.2.3.4) is the real IPv4 client.
    if host.startswith("::ffff:"):
        mapped = host.split(":", 1)[-1] if False else host[7:]
        if mapped.count(".") == 3:
            return mapped
    return host


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    api_host: str,
    api_port: int,
) -> None:
    try:
        head, rest = await _read_head(reader)
        rewritten = rewrite_request(head, _peer_ip(writer))
    except Exception as exc:
        sys.stderr.write(f"web proxy: rejected client ({exc})\n")
        writer.close()
        return
    try:
        upstream_r, upstream_w = await asyncio.open_connection(api_host, api_port)
    except OSError as exc:
        sys.stderr.write(f"web proxy: API {api_host}:{api_port} unreachable ({exc})\n")
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    upstream_w.write(rewritten + b"\r\n" + rest)
    await upstream_w.drain()
    await asyncio.gather(_pump(reader, upstream_w), _pump(upstream_r, writer))


def _config() -> tuple[str, int, str, int]:
    web_host = os.environ.get("VOICESTUDIO_WEB_HOST", "0.0.0.0").strip() or "0.0.0.0"
    web_port = int(os.environ.get("VOICESTUDIO_WEB_PORT", "8787"))
    api_host = os.environ.get("VOICESTUDIO_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    api_port = int(os.environ.get("VOICESTUDIO_API_PORT", os.environ.get("OMNIVOICE_PORT", "3900")))
    return web_host, web_port, api_host, api_port


async def serve() -> None:
    web_host, web_port, api_host, api_port = _config()

    async def _connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await handle_client(reader, writer, api_host, api_port)

    server = await asyncio.start_server(_connected, web_host, web_port)
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    sys.stderr.write(f"web proxy: listening on {sockets} -> {api_host}:{api_port}\n")
    async with server:
        await server.serve_forever()


def _assert(cond: bool, message: str) -> None:
    if not cond:
        raise SystemExit(message)


def _self_test_headers() -> None:
    raw = (
        "GET /engines HTTP/1.1\r\n"
        "Host: 203.0.113.8:8787\r\n"
        "X-Forwarded-For: 127.0.0.1\r\n"
        "X-Forwarded-Proto: https\r\n"
        "Connection: keep-alive\r\n"
        "\r\n"
    ).encode()
    out = rewrite_request(raw, "203.0.113.9").decode("iso-8859-1")
    _assert("X-Forwarded-For: 203.0.113.9" in out, out)
    _assert("X-Forwarded-For: 127.0.0.1" not in out, out)
    _assert("X-Forwarded-Proto: http" in out, out)
    _assert("X-Forwarded-Proto: https" not in out, out)
    _assert("Connection: close" in out, out)
    _assert("Host: 203.0.113.8:8787" in out, out)

    ws = (
        "GET /ws/events HTTP/1.1\r\n"
        "Host: 203.0.113.8:8787\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "\r\n"
    ).encode()
    upgraded = rewrite_request(ws, "203.0.113.9").decode("iso-8859-1")
    _assert("Connection: Upgrade" in upgraded, upgraded)
    _assert("Upgrade: websocket" in upgraded, upgraded)
    _assert("Connection: close" not in upgraded, upgraded)


async def _self_test_socket() -> None:
    captured: list[bytes] = []

    async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = b""
        while b"\r\n\r\n" not in data:
            data += await reader.read(4096)
        captured.append(data)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        await writer.drain()
        writer.close()

    backend = await asyncio.start_server(upstream, "127.0.0.1", 0)
    api_port = backend.sockets[0].getsockname()[1]

    async def connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await handle_client(reader, writer, "127.0.0.1", api_port)

    proxy = await asyncio.start_server(connected, "127.0.0.1", 0)
    proxy_port = proxy.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
    writer.write(
        b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Forwarded-For: 127.0.0.1\r\n\r\n"
    )
    await writer.drain()
    body = await reader.read()
    writer.close()
    proxy.close()
    backend.close()
    await proxy.wait_closed()
    await backend.wait_closed()
    _assert(body.endswith(b"ok"), repr(body))
    seen = captured[0].decode("iso-8859-1")
    # The proxy's own peer is loopback in this test; the spoofed header is gone
    # and exactly one forwarded-for remains.
    _assert(seen.count("X-Forwarded-For:") == 1, seen)
    _assert("X-Forwarded-For: 127.0.0.1" in seen, seen)


def main() -> None:
    if "--self-test" in sys.argv[1:]:
        _self_test_headers()
        asyncio.run(_self_test_socket())
        print("web proxy self-test passed")
        return
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
