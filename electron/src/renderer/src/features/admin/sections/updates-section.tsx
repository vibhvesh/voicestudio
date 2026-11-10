import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminGet, adminSend } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface UpdateStatus {
  version: string;
  sha: string;
  latest_sha: string;
  ref: string;
  update_available: boolean;
  remote_error: string;
  changelog: string;
  log: string;
  job: { running: boolean; ok: boolean | null; detail: string };
}

export function UpdatesSection() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['admin-updates'],
    queryFn: () => adminGet<UpdateStatus>('/admin/updates'),
    refetchInterval: (q) => (q.state.data?.job.running ? 2000 : false),
  });
  const run = useMutation({
    mutationFn: () => adminSend<{ ok: boolean; detail: string }>('/admin/updates/run', 'POST'),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['admin-updates'] }),
  });
  const data = query.data;
  return (
    <>
      <AdminHeader
        title="Updates"
        detail="Compares this checkout with origin and runs scripts/update.sh. Models and the API key stay where they are."
      />
      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Installed</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <p className="font-medium">{data?.version || '…'}</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{data?.sha || '—'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Latest on {data?.ref || 'main'}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <p className="font-medium">
              {data ? (data.update_available ? 'Update available' : data.latest_sha ? 'Current' : 'Unknown') : '…'}
            </p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{data?.latest_sha || '—'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Action</CardTitle>
          </CardHeader>
          <CardContent>
            <Button disabled={run.isPending || data?.job.running} onClick={() => run.mutate()}>
              {data?.job.running ? 'Updating…' : 'Update now'}
            </Button>
            {run.data?.detail ? <p className="mt-2 text-xs text-muted-foreground">{run.data.detail}</p> : null}
          </CardContent>
        </Card>
      </div>
      {data?.remote_error ? (
        <p className="text-sm text-destructive">Could not read origin: {data.remote_error}</p>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>Changelog</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
            {data?.changelog || 'No changelog in this checkout.'}
          </pre>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Update log</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
            {data?.log || 'No update has been run from this panel yet.'}
          </pre>
        </CardContent>
      </Card>
    </>
  );
}
