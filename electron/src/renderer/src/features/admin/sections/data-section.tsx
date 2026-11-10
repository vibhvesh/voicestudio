import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { adminGet, adminSend, formatBytes } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface DataUsage {
  data_dir: string;
  data_bytes: number;
  outputs_dir: string;
  outputs_bytes: number;
  database_bytes: number;
  models_dir: string;
  models_bytes: number;
}

export function DataSection() {
  const queryClient = useQueryClient();
  const [days, setDays] = useState('30');
  const [note, setNote] = useState('');
  const query = useQuery({
    queryKey: ['admin-data'],
    queryFn: () => adminGet<DataUsage>('/admin/data'),
  });
  const cleanup = useMutation({
    mutationFn: () =>
      adminSend<DataUsage>('/admin/data/cleanup', 'POST', {
        older_than_days: Number(days) || 0,
        confirm: true,
      }),
    onSuccess: async (result) => {
      setNote(`Removed files. ${formatBytes(result.outputs_bytes)} of generated audio remains.`);
      await queryClient.invalidateQueries({ queryKey: ['admin-data'] });
    },
    onError: (error: Error) => setNote(error.message),
  });
  const data = query.data;
  const exportHref = (secrets: boolean) => {
    const base = window.location.origin;
    return `${base}/admin/data/export?include_secrets=${secrets ? 'true' : 'false'}`;
  };
  return (
    <>
      <AdminHeader
        title="Data"
        detail="Where projects, generated audio, and model weights live. Cleanup only deletes files under the generated-audio folder."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <Usage label="App data" path={data?.data_dir} bytes={data?.data_bytes} />
        <Usage label="Generated audio" path={data?.outputs_dir} bytes={data?.outputs_bytes} />
        <Usage label="Database" path="omnivoice.db" bytes={data?.database_bytes} />
        <Usage label="Models" path={data?.models_dir || 'Hugging Face cache'} bytes={data?.models_bytes} />
      </div>
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border/70 p-4">
        <label className="grid gap-1 text-sm">
          Delete audio older than (days)
          <Input className="w-28" value={days} onChange={(event) => setDays(event.target.value)} />
          <span className="text-xs text-muted-foreground">0 deletes every generated file.</span>
        </label>
        <Button variant="secondary" disabled={cleanup.isPending} onClick={() => cleanup.mutate()}>
          Clean generated audio
        </Button>
        {note ? <p className="text-sm text-muted-foreground">{note}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <a className="inline-flex h-8 items-center rounded-md bg-secondary px-3 text-sm" href={exportHref(false)}>
          Export config
        </a>
        <a className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm" href={exportHref(true)}>
          Export config with secrets
        </a>
      </div>
    </>
  );
}

function Usage({ label, path, bytes }: { label: string; path?: string; bytes?: number }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{bytes === undefined ? '…' : formatBytes(bytes)}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{path}</p>
    </div>
  );
}
