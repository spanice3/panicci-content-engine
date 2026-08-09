// Panicci Content Engine — serves the format library so the frontend has one
// source of truth instead of duplicating the list in index.html.
// GET only. Optionally merges in live perf scores when Supabase env vars are set.

const { withPerf } = require("../lib/formats");
const { fetchPerfByFormatId } = require("../lib/performance-store");

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "Use GET" }); return; }

  let perfByFormatId = null;
  try {
    perfByFormatId = await fetchPerfByFormatId();
  } catch (_) {
    // Performance store not configured yet — formats still work without it.
  }

  res.status(200).json({ formats: withPerf(perfByFormatId) });
};
