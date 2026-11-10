"""Installed and available models, with the existing download pipeline."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class InstallBody(BaseModel):
    repo_id: str


def _disk() -> dict:
    path = "/"
    try:
        from api.routers.setup.models import hf_cache_dir
        path = hf_cache_dir() or "/"
    except Exception:
        path = "/"
    usage = shutil.disk_usage(path if os_path_exists(path) else "/")
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def os_path_exists(path: str) -> bool:
    import os
    return os.path.isdir(path)


@router.get("/models")
def models_list():
    from api.routers.setup.download import model_install_status
    from api.routers.setup.models import list_models

    catalogue = list_models()
    models = catalogue.get("models", [])
    summary = {
        "count": len(models),
        "installed": sum(1 for item in models if item.get("installed")),
        "installed_bytes": catalogue.get("total_installed_bytes") or 0,
    }
    return {
        "summary": summary,
        "disk": _disk(),
        "cache_dir": catalogue.get("hf_cache_dir"),
        "jobs": model_install_status().get("jobs", []),
        "models": [
            {
                "repo_id": item.get("repo_id"),
                "hf_repo": item.get("hf_repo") or item.get("repo_id"),
                "label": item.get("label"),
                "role": item.get("role"),
                "size_gb": item.get("size_gb"),
                "installed": bool(item.get("installed")),
                "incomplete": bool(item.get("incomplete")),
                "size_on_disk_bytes": item.get("size_on_disk_bytes") or 0,
            }
            for item in models
        ],
    }


@router.post("/models/install")
async def models_install(body: InstallBody):
    from api.routers.setup.download import InstallModelRequest, install_model

    if not body.repo_id.strip():
        raise HTTPException(status_code=422, detail="Choose a model to download.")
    return await install_model(InstallModelRequest(repo_id=body.repo_id.strip(), target="local"))


@router.delete("/models/{repo_id:path}")
def models_delete(repo_id: str):
    from api.routers.setup.download import delete_model

    return delete_model(repo_id)
