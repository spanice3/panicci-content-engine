// Panicci Content Engine — thin REST client for the shared `format_performance`
// table in the panicci-hub Supabase project. Every studio tool that logs content
// performance writes to the same table, so the format-selection data compounds
// across every client, not just this one — that cross-client pool is the point.
//
// No @supabase/supabase-js dependency on purpose: this repo ships zero npm deps
// today (see package.json), and PostgREST over fetch is all a few small
// serverless functions need. Same pattern as the Anthropic call in
// api/generate-questions.js — plain fetch, key read server-side only.
//
// Env vars (set in Vercel, never committed):
//   SUPABASE_URL              e.g. https://xxxx.supabase.co
//   SUPABASE_SERVICE_ROLE_KEY server-side only — never expose to the browser

const TABLE = "format_performance";

function config() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return { url: url.replace(/\/$/, ""), key };
}

async function insertPerformanceLog(entry) {
  const cfg = config();
  if (!cfg) throw new Error("not_configured");

  const row = {
    format_id: entry.formatId,
    niche: entry.niche || null,
    client: entry.client || null,
    platform: entry.platform,
    posted_at: entry.postedAt || new Date().toISOString(),
    views: entry.views,
    watch_through_pct: entry.watchThroughPct != null ? entry.watchThroughPct : null,
    notes: entry.notes || null
  };

  const r = await fetch(`${cfg.url}/rest/v1/${TABLE}`, {
    method: "POST",
    headers: {
      apikey: cfg.key,
      authorization: `Bearer ${cfg.key}`,
      "content-type": "application/json",
      prefer: "return=representation"
    },
    body: JSON.stringify(row)
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(`supabase_insert_failed: ${r.status} ${detail.slice(0, 300)}`);
  }
  const data = await r.json();
  return data[0] || row;
}

// Aggregates raw rows into { [formatId]: { postCount, avgViews, avgWatchThroughPct } }.
// Optionally scoped to one niche so generation can favor what works for THIS niche,
// not just what's popular studio-wide.
async function fetchPerfByFormatId(niche) {
  const cfg = config();
  if (!cfg) return null;

  const params = new URLSearchParams({
    select: "format_id,views,watch_through_pct",
    limit: "2000"
  });
  if (niche) params.set("niche", `eq.${niche}`);

  const r = await fetch(`${cfg.url}/rest/v1/${TABLE}?${params.toString()}`, {
    headers: { apikey: cfg.key, authorization: `Bearer ${cfg.key}` }
  });
  if (!r.ok) throw new Error(`supabase_read_failed: ${r.status}`);
  const rows = await r.json();

  const byFormat = {};
  for (const row of rows) {
    const id = row.format_id;
    if (!id) continue;
    if (!byFormat[id]) byFormat[id] = { postCount: 0, viewsSum: 0, watchSum: 0, watchCount: 0 };
    const bucket = byFormat[id];
    bucket.postCount += 1;
    bucket.viewsSum += Number(row.views) || 0;
    if (row.watch_through_pct != null) { bucket.watchSum += Number(row.watch_through_pct); bucket.watchCount += 1; }
  }

  const out = {};
  for (const [id, b] of Object.entries(byFormat)) {
    out[id] = {
      postCount: b.postCount,
      avgViews: Math.round(b.viewsSum / b.postCount),
      avgWatchThroughPct: b.watchCount ? Math.round((b.watchSum / b.watchCount) * 10) / 10 : null
    };
  }
  return out;
}

// Ranks formats by avgViews for a niche, for the generator to bias toward.
// Returns [] (not an error) when the store isn't configured or has no data yet —
// callers should treat that as "no signal," not a failure.
async function topFormatsForNiche(niche, limit) {
  let byFormat;
  try { byFormat = await fetchPerfByFormatId(niche); } catch (_) { return []; }
  if (!byFormat) return [];
  return Object.entries(byFormat)
    .filter(([, v]) => v.postCount >= 2) // require repeat data before trusting a format
    .sort((a, b) => b[1].avgViews - a[1].avgViews)
    .slice(0, limit || 5)
    .map(([formatId, v]) => ({ formatId, ...v }));
}

module.exports = { insertPerformanceLog, fetchPerfByFormatId, topFormatsForNiche };
