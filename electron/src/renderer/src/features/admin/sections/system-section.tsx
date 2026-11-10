import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { adminGet, adminSend, formatBytes } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';

interface SystemStatus {
  version: string;
  cpu_percent: number;
  cpu_count: number;
  memory: { percent: number; used_bytes: number; total_bytes: number };
  disk: { percent: number; free_bytes: number; total_bytes: number };
  gpu: { available: boolean; name: string; memory_bytes: number };
  torch_variant: string;
  device: string;
  services: { ok: boolean; output?: string; detail?: string };
  logs: string[];
}

export function SystemSection() {
  const [logName, setLogName] = useState('api');
  const [note, setNote] = useState('');
  const system = useQuery({
    queryKey: ['admin-system'],
    queryFn: () => adminGet<SystemStatus>('/admin/system'),
    refetchInterval: 5000,
  });
  const logs = useQuery({
    queryKey: ['admin-log', logName],
    queryFn: () => adminGet<{ text: string }>(`/admin/system/logs?name=${encodeURIComponent(logName)}`),
  });
  const action = useMutation({
    mutationFn: (name: 'restart' | 'stop') => adminSend('/admin/system/action', 'POST', { action: name }),
    onSuccess: (_data, name) => setNote(name === 'stop' ? 'Stop scheduled.' : 'Restart scheduled.'),
    onError: (error: Error) => setNote(error.message),
  });
  const data = system.data;
  return (
    <>
      <AdminHeader
        title="System"
        detail="Live CPU, memory, disk, and the API and web processes. Restart and stop go through the service helper."
      />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={action.isPending} onClick={() => action.mutate('restart')}>
          Restart
        </Button>
        <Button size="sm" variant="secondary" disabled={action.isPending} onClick={() => action.mutate('stop')}>
          Stop
        </Button>
        {note ? <span className="self-center text-sm text-muted-foreground">{note}</span> : null}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Meter label="CPU" percent={data?.cpu_percent || 0} hint={data ? `${data.cpu_count} cores` : ''} />
        <Meter
          label="Memory"
          percent={data?.memory.percent || 0}
          hint={data ? `${formatBytes(data.memory.used_bytes)} of ${formatBytes(data.memory.total_bytes)}` : ''}
        />
        <Meter
          label="Disk"
          percent={data?.disk.percent || 0}
          hint={data ? `${formatBytes(data.disk.free_bytes)} free` : ''}
        />
        <div className="rounded-xl border border-border/70 bg-card p-4 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Compute</p>
          <p className="mt-2 font-medium">{data?.gpu.available ? data.gpu.name : 'CPU only'}</p>
          <p className="mt-1 text-muted-foreground">
            PyTorch {data?.torch_variant || '—'} · device {data?.device || '—'}
          </p>
          <p className="mt-1 text-muted-foreground">Version {data?.version || '—'}</p>
        </div>
      </div>
      <pre className="max-h-32 overflow-auto rounded-xl border border-border/70 bg-muted/30 p-3 text-xs">
        {data?.services.output || data?.services.detail || 'No service status yet.'}
      </pre>
      <div className="flex flex-wrap gap-2">
        {['api', 'web', 'update', 'omnivoice.log'].map((name) => (
          <Button
            key={name}
            size="sm"
            variant={logName === name ? 'secondary' : 'ghost'}
            onClick={() => setLogName(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      <pre className="max-h-80 overflow-auto rounded-xl border border-border/70 bg-card p-3 text-xs leading-relaxed">
        {logs.data?.text || (logs.isError ? 'That log is not available yet.' : 'Loading log…')}
      </pre>
    </>
  );
}

function Meter({ label, percent, hint }: { label: string; percent: number; hint: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-4">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="tabular-nums text-muted-foreground">{Math.round(percent)}%</span>
      </div>
      <Progress value={Math.max(0, Math.min(100, percent))} />
      <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
