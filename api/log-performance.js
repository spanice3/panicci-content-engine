// Panicci Content Engine — records a posted clip's real-world performance
// against the format it was built on. This is the feedback loop: without it,
// the format library is just a static guess, same as any competitor's.
// POST { formatId, niche, client, platform, views, watchThroughPct, notes }.

const { byId } = require("../lib/formats");
const { insertPerformanceLog } = require("../lib/performance-store");

const PLATFORMS = new Set(["instagram_reels", "tiktok", "facebook", "linkedin", "youtube_shorts"]);

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "Use POST" }); return; }

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};

  const formatId = (body.formatId || "").toString().trim();
  const niche = (body.niche || "").toString().slice(0, 200).trim();
  const client = (body.client || "").toString().slice(0, 200).trim();
  const platform = (body.platform || "").toString().trim();
  const views = Number(body.views);
  const watchThroughPct = body.watchThroughPct != null && body.watchThroughPct !== ""
    ? Math.max(0, Math.min(100, Number(body.watchThroughPct))) : null;
  const notes = (body.notes || "").toString().slice(0, 1000).trim();

  if (!byId(formatId)) { res.status(400).json({ error: "invalid_format", message: "Unknown format id — reload the format list and try again." }); return; }
  if (!niche) { res.status(400).json({ error: "missing_niche", message: "Which niche was this clip for?" }); return; }
  if (!PLATFORMS.has(platform)) { res.status(400).json({ error: "invalid_platform", message: "Unknown platform." }); return; }
  if (!Number.isFinite(views) || views < 0) { res.status(400).json({ error: "invalid_views", message: "Views must be a non-negative number." }); return; }

  try {
    const row = await insertPerformanceLog({ formatId, niche, client, platform, views, watchThroughPct, notes });
    res.status(200).json({ ok: true, row });
  } catch (err) {
    if (err && err.message === "not_configured") {
      res.status(503).json({
        error: "not_configured",
        message: "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set in Vercel yet. Add them under Project → Settings → Environment Variables, then redeploy."
      });
      return;
    }
    res.status(500).json({ error: "server_error", message: (err && err.message) || "unknown" });
  }
};
