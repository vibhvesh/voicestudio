import type { ReactElement } from 'react';
import { useParams } from '@tanstack/react-router';
import { AdminShell } from './admin-shell';
import type { AdminSection } from './api';
import { AccessSection } from './sections/access-section';
import { DataSection } from './sections/data-section';
import { ModelsSection } from './sections/models-section';
import { OverviewSection } from './sections/overview-section';
import { SettingsSection } from './sections/settings-section';
import { SystemSection } from './sections/system-section';
import { UpdatesSection } from './sections/updates-section';

const sections: Record<AdminSection, () => ReactElement> = {
  overview: OverviewSection,
  updates: UpdatesSection,
  settings: SettingsSection,
  models: ModelsSection,
  system: SystemSection,
  access: AccessSection,
  data: DataSection,
};

export function AdminPage() {
  const params = useParams({ strict: false }) as { section?: string };
  const key = (params.section || 'overview') as AdminSection;
  const Section = sections[key] || OverviewSection;
  return (
    <AdminShell>
      <Section />
    </AdminShell>
  );
}
