import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { adminGet, adminSections, formatBytes } from '../api';
import { AdminHeader } from '../admin-shell';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface SystemStatus {
  version: string;
  cpu_percent: number;
  memory: { percent: number; used_bytes: number; total_bytes: number };
  disk: { percent: number; free_bytes: number };
  gpu: { available: boolean; name: string };
  services: { ok: boolean; output?: string };
}

interface UpdateStatus {
  version: string;
  sha: string;
  latest_sha: string;
  update_available: boolean;
}

export function OverviewSection() {
  const system = useQuery({
    queryKey: ['admin-system'],
    queryFn: () => adminGet<SystemStatus>('/admin/system'),
  });
  const updates = useQuery({
    queryKey: ['admin-updates'],
    queryFn: () => adminGet<UpdateStatus>('/admin/updates'),
  });
  const data = system.data;
  return (
    <>
      <AdminHeader
        title="Overview"
        detail="Health, version, and the places you change the server. Remote browsers need the API key; this machine's loopback does not."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Version" value={data?.version || updates.data?.version || '…'} />
        <Stat
          label="Update"
          value={
            updates.data ? (updates.data.update_available ? 'Available' : 'Up to date') : '…'
          }
        />
        <Stat label="CPU" value={data ? `${Math.round(data.cpu_percent)}%` : '…'} />
        <Stat
          label="Memory"
          value={data ? `${Math.round(data.memory.percent)}%` : '…'}
          hint={data ? `${formatBytes(data.memory.used_bytes)} / ${formatBytes(data.memory.total_bytes)}` : ''}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Services</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-muted-foreground">
            {data?.gpu.available ? `GPU ${data.gpu.name}` : 'CPU inference. No NVIDIA GPU reported.'}
          </p>
          <pre className="max-h-28 overflow-auto rounded-lg bg-muted/40 p-3 text-xs">
            {data?.services.output || (system.isError ? 'Could not read service status.' : 'Checking…')}
          </pre>
        </CardContent>
      </Card>
      <div className="grid gap-3 sm:grid-cols-2">
        {adminSections
          .filter((section) => section.id !== 'overview')
          .map((section) => (
            <Link
              key={section.id}
              to="/admin/$section"
              params={{ section: section.id }}
              className="rounded-xl border border-border/70 bg-card px-4 py-3 transition-colors hover:bg-accent/40"
            >
              <span className="block text-sm font-medium">{section.label}</span>
              <span className="mt-1 block text-xs text-muted-foreground">{section.hint}</span>
            </Link>
          ))}
      </div>
    </>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xl font-semibold tabular-nums">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
