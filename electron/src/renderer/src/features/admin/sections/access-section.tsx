import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { adminGet, adminSend } from '../api';
import { AdminHeader } from '../admin-shell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface AccessState {
  configured: boolean;
  preview: string;
  path: string;
  writable: boolean;
}

interface RotateResult {
  ok: boolean;
  api_key: string;
  detail: string;
}

export function AccessSection() {
  const queryClient = useQueryClient();
  const [revealed, setRevealed] = useState('');
  const query = useQuery({
    queryKey: ['admin-access'],
    queryFn: () => adminGet<AccessState>('/admin/access'),
  });
  const rotate = useMutation({
    mutationFn: (path: string) => adminSend<RotateResult>(path, 'POST'),
    onSuccess: async (result) => {
      setRevealed(result.api_key);
      await queryClient.invalidateQueries({ queryKey: ['admin-access'] });
    },
  });
  const data = query.data;
  return (
    <>
      <AdminHeader
        title="Access"
        detail="The API key is the remote administrator credential. Loopback clients on this machine do not need it. Rotating or revoking replaces the key immediately."
      />
      <Card>
        <CardHeader>
          <CardTitle>API key</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p>{data?.configured ? `Configured (${data.preview})` : 'Not configured'}</p>
          <p className="text-muted-foreground">{data?.path}</p>
          {data && !data.writable ? (
            <p className="text-destructive">The env file is not writable, so the key cannot be changed from here.</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button disabled={!data?.writable || rotate.isPending} onClick={() => rotate.mutate('/admin/access/rotate')}>
              {data?.configured ? 'Rotate key' : 'Generate key'}
            </Button>
            <Button
              variant="secondary"
              disabled={!data?.configured || !data?.writable || rotate.isPending}
              onClick={() => rotate.mutate('/admin/access/revoke')}
            >
              Revoke key
            </Button>
          </div>
          {revealed ? (
            <div className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-3">
              <p className="text-xs text-amber-200">Copy this key now. It will not be shown again.</p>
              <p className="mt-2 break-all font-mono text-sm">{revealed}</p>
              <p className="mt-2 text-xs text-muted-foreground">{rotate.data?.detail}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </>
  );
}
