import { apiJson } from '@/lib/api/client';

export type AdminSection = 'overview' | 'updates' | 'settings' | 'models' | 'system' | 'access' | 'data';

export const adminSections: { id: AdminSection; label: string; hint: string }[] = [
  { id: 'overview', label: 'Overview', hint: 'Status at a glance' },
  { id: 'updates', label: 'Updates', hint: 'Version and changelog' },
  { id: 'settings', label: 'Settings', hint: 'Environment and endpoints' },
  { id: 'models', label: 'Models', hint: 'Download and disk' },
  { id: 'system', label: 'System', hint: 'Resources, services, logs' },
  { id: 'access', label: 'Access', hint: 'API key' },
  { id: 'data', label: 'Data', hint: 'Storage and backup' },
];

export function adminGet<T>(path: string): Promise<T> {
  return apiJson<T>(path);
}

export function adminSend<T>(path: string, method: string, body?: unknown): Promise<T> {
  return apiJson<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}
