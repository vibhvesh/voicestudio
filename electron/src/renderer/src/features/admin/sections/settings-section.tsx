import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { adminGet, adminSend } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface SettingRow {
  key: string;
  label: string;
  group: string;
  kind: string;
  help: string;
  options?: string[];
  value: string;
  configured: boolean;
  restart_required: boolean;
  restart: boolean;
}

interface SettingsResponse {
  path: string;
  writable: boolean;
  restart_required: boolean;
  settings: SettingRow[];
}

export function SettingsSection() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['admin-settings'],
    queryFn: () => adminGet<SettingsResponse>('/admin/settings'),
  });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  useEffect(() => {
    if (!query.data) return;
    const next: Record<string, string> = {};
    for (const row of query.data.settings) next[row.key] = row.kind === 'secret' ? '' : row.value;
    setDraft(next);
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => {
      const changes = (query.data?.settings || [])
        .filter((row) => {
          const next = draft[row.key] ?? '';
          if (row.kind === 'secret') return next.trim().length > 0;
          return next !== row.value;
        })
        .map((row) => ({ key: row.key, value: draft[row.key] ?? '' }));
      return adminSend<SettingsResponse>('/admin/settings', 'PUT', { changes });
    },
    onSuccess: async () => {
      setMessage('Saved.');
      await queryClient.invalidateQueries({ queryKey: ['admin-settings'] });
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const restart = useMutation({
    mutationFn: () => adminSend('/admin/system/action', 'POST', { action: 'restart' }),
    onSuccess: () => setMessage('Restart scheduled. This page will reconnect in a few seconds.'),
  });
  const data = query.data;
  const groups = [...new Set((data?.settings || []).map((row) => row.group))];
  return (
    <>
      <AdminHeader
        title="Settings"
        detail="Environment options for this server. Secrets stay masked until you type a replacement. Empty secret fields are left unchanged."
      />
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">{data?.path}</span>
        {data && !data.writable ? (
          <span className="text-destructive">File is not writable by the service.</span>
        ) : null}
        {data?.restart_required ? (
          <span className="text-amber-300">Restart required for some changes.</span>
        ) : null}
        <Button size="sm" variant="secondary" disabled={restart.isPending} onClick={() => restart.mutate()}>
          Restart services
        </Button>
        <Button size="sm" disabled={save.isPending || !data?.writable} onClick={() => save.mutate()}>
          Save
        </Button>
      </div>
      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {groups.map((group) => (
        <Card key={group}>
          <CardHeader>
            <CardTitle>{group}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {(data?.settings || [])
              .filter((row) => row.group === group)
              .map((row) => (
                <label key={row.key} className="grid gap-1.5">
                  <span className="flex items-center justify-between gap-3 text-sm font-medium">
                    {row.label}
                    {row.restart_required ? (
                      <span className="text-xs font-normal text-amber-300">Restart required</span>
                    ) : null}
                  </span>
                  {row.kind === 'enum' ? (
                    <select
                      className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                      value={draft[row.key] ?? ''}
                      onChange={(event) => setDraft((prev) => ({ ...prev, [row.key]: event.target.value }))}
                    >
                      {(row.options || []).map((option) => (
                        <option key={option || 'empty'} value={option}>
                          {option || 'Automatic'}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      type={row.kind === 'secret' ? 'password' : 'text'}
                      autoComplete="off"
                      placeholder={row.kind === 'secret' && row.configured ? 'Configured — enter a new value to replace' : ''}
                      value={draft[row.key] ?? ''}
                      onChange={(event) => setDraft((prev) => ({ ...prev, [row.key]: event.target.value }))}
                    />
                  )}
                  <span className="text-xs text-muted-foreground">{row.help}</span>
                </label>
              ))}
          </CardContent>
        </Card>
      ))}
    </>
  );
}
