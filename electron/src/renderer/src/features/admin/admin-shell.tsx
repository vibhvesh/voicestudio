import { Link, useParams } from '@tanstack/react-router';
import {
  ActivityIcon,
  DatabaseIcon,
  HardDriveIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  RefreshCwIcon,
  Settings2Icon,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { adminSections, type AdminSection } from './api';
import { cn } from '@/lib/utils';

const icons: Record<AdminSection, typeof ActivityIcon> = {
  overview: LayoutDashboardIcon,
  updates: RefreshCwIcon,
  settings: Settings2Icon,
  models: HardDriveIcon,
  system: ActivityIcon,
  access: KeyRoundIcon,
  data: DatabaseIcon,
};

export function AdminShell({ children }: { children: ReactNode }) {
  const params = useParams({ strict: false }) as { section?: string };
  const current = (params.section || 'overview') as AdminSection;
  return (
    <div className="flex h-full min-h-0 bg-background text-foreground">
      <nav
        aria-label="Admin"
        className="flex w-52 shrink-0 flex-col gap-1 border-r border-border/60 bg-sidebar p-3"
      >
        <div className="px-2 pb-3 pt-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Admin
          </p>
          <p className="mt-1 text-sm text-sidebar-foreground/80">Server control</p>
        </div>
        {adminSections.map((section) => {
          const Icon = icons[section.id];
          const active = current === section.id;
          return (
            <Link
              key={section.id}
              to={section.id === 'overview' ? '/admin' : '/admin/$section'}
              params={section.id === 'overview' ? undefined : { section: section.id }}
              className={cn(
                'flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-sidebar-foreground/80 outline-none transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-ring',
                active && 'bg-sidebar-accent text-sidebar-foreground',
              )}
            >
              <Icon className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0">
                <span className="block truncate">{section.label}</span>
                <span className="block truncate text-[11px] text-muted-foreground">{section.hint}</span>
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6">{children}</div>
      </div>
    </div>
  );
}

export function AdminHeader({ title, detail }: { title: string; detail: string }) {
  return (
    <header>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{detail}</p>
    </header>
  );
}
