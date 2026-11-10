import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { adminGet, adminSend, formatBytes } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';

interface ModelRow {
  repo_id: string;
  label: string;
  role: string;
  size_gb: number;
  installed: boolean;
  incomplete: boolean;
  size_on_disk_bytes: number;
}

interface ModelsResponse {
  summary: { count: number; installed: number; installed_bytes: number };
  disk: { free_bytes: number; total_bytes: number; used_bytes: number };
  jobs: { repo_id: string; state: string; pct?: number }[];
  models: ModelRow[];
}

export function ModelsSection() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('');
  const [message, setMessage] = useState('');
  const query = useQuery({
    queryKey: ['admin-models'],
    queryFn: () => adminGet<ModelsResponse>('/admin/models'),
    refetchInterval: (q) => ((q.state.data?.jobs.length || 0) > 0 ? 2000 : false),
  });
  const install = useMutation({
    mutationFn: (repo_id: string) => adminSend('/admin/models/install', 'POST', { repo_id }),
    onSuccess: () => {
      setMessage('Download started.');
      void queryClient.invalidateQueries({ queryKey: ['admin-models'] });
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const remove = useMutation({
    mutationFn: (repo_id: string) => adminSend(`/admin/models/${encodeURIComponent(repo_id)}`, 'DELETE'),
    onSuccess: () => {
      setMessage('Model removed.');
      void queryClient.invalidateQueries({ queryKey: ['admin-models'] });
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const data = query.data;
  const needle = filter.trim().toLowerCase();
  const rows = (data?.models || []).filter((row) =>
    !needle || `${row.label} ${row.repo_id} ${row.role}`.toLowerCase().includes(needle),
  );
  const diskPercent = data ? Math.round((data.disk.used_bytes / data.disk.total_bytes) * 100) : 0;
  return (
    <>
      <AdminHeader
        title="Models"
        detail="Catalogue from the server. Downloads use the same installer as Settings. Nothing is fetched until you click Download."
      />
      <div className="grid gap-3 sm:grid-cols-3">
        <Info label="Installed" value={data ? `${data.summary.installed} / ${data.summary.count}` : '…'} />
        <Info label="On disk" value={data ? formatBytes(data.summary.installed_bytes) : '…'} />
        <Info label="Disk free" value={data ? formatBytes(data.disk.free_bytes) : '…'} />
      </div>
      <div>
        <div className="mb-1 flex justify-between text-xs text-muted-foreground">
          <span>Disk</span>
          <span>{data ? `${diskPercent}%` : ''}</span>
        </div>
        <Progress value={diskPercent} />
      </div>
      {(data?.jobs || []).map((job) => (
        <p key={job.repo_id} className="text-sm text-muted-foreground">
          {job.state}: {job.repo_id}
          {typeof job.pct === 'number' ? ` · ${Math.round(job.pct)}%` : ''}
        </p>
      ))}
      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      <Input
        placeholder="Filter models"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <div className="overflow-hidden rounded-xl border border-border/70">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Model</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Size</th>
              <th className="px-3 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.repo_id} className="border-t border-border/60">
                <td className="px-3 py-2">
                  <span className="block font-medium">{row.label}</span>
                  <span className="block font-mono text-[11px] text-muted-foreground">{row.repo_id}</span>
                </td>
                <td className="px-3 py-2 text-muted-foreground">{row.role}</td>
                <td className="px-3 py-2 tabular-nums text-muted-foreground">
                  {row.installed ? formatBytes(row.size_on_disk_bytes) : `${row.size_gb ?? '—'} GB`}
                </td>
                <td className="px-3 py-2 text-right">
                  {row.installed ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(row.repo_id)}
                    >
                      Delete
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" disabled={install.isPending} onClick={() => install.mutate(row.repo_id)}>
                      Download
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}
