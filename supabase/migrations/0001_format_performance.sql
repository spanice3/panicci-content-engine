-- Panicci Ventures Hub (project ref: sehnpskesbxgpdwknvvq) — format_performance
-- Already applied directly to the panicci-hub Supabase project. Kept here so the
-- schema lives in version control and any other studio tool that writes to this
-- same table can see the shape without needing DB access.

create table if not exists public.format_performance (
  id uuid primary key default gen_random_uuid(),
  format_id text not null,
  niche text not null,
  client text,
  platform text not null,
  posted_at timestamptz not null default now(),
  views bigint not null default 0,
  watch_through_pct numeric,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists format_performance_format_id_idx on public.format_performance (format_id);
create index if not exists format_performance_niche_idx on public.format_performance (niche);

alter table public.format_performance enable row level security;

-- Service role (used server-side only, via SUPABASE_SERVICE_ROLE_KEY) bypasses RLS by
-- default, so the API routes work with no policy needed. No anon/public policy is
-- created — this table is never read or written directly from the browser.
