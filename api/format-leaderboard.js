// Panicci Content Engine — ranks formats by real posted-clip performance.
// GET /api/format-leaderboard?niche=... (niche optional — omit for studio-wide).
// This is what turns "we think these formats work" into "we know these formats
// work, across every client we've shot for" — the actual moat, not the pitch for it.

const { byId } = require("../lib/formats");
const { fetchPerfByFormatId } = require("../lib/performance-store");

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "Use GET" }); return; }

  const niche = (req.query && req.query.niche) ? req.query.niche.toString().slice(0, 200).trim() : "";

  let byFormat;
  try {
    byFormat = await fetchPerfByFormatId(niche || undefined);
  } catch (err) {
    res.status(500).json({ error: "server_error", message: (err && err.message) || "unknown" });
    return;
  }
  if (byFormat === null) {
    res.status(503).json({
      error: "not_configured",
      message: "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set in Vercel yet. Add them under Project → Settings → Environment Variables, then redeploy."
    });
    return;
  }

  const leaderboard = Object.entries(byFormat)
    .map(([formatId, stats]) => {
      const fmt = byId(formatId);
      return {
        formatId,
        formatName: fmt ? fmt.name : formatId,
        category: fmt ? fmt.category : null,
        postCount: stats.postCount,
        avgViews: stats.avgViews,
        avgWatchThroughPct: stats.avgWatchThroughPct
      };
    })
    .sort((a, b) => b.avgViews - a.avgViews);

  res.status(200).json({ niche: niche || null, leaderboard });
};
