// Panicci Content Engine — shared request guards for the /api functions.
// (Files under api/_lib are helpers, not routes: Vercel skips paths starting with "_".)
//
//   allowOrigin(req, res, headers) -> CORS locked to the studio's own hosts. A browser request from
//                                     any other origin gets a 403; server-side callers send no Origin.
//   studioKeyOk(req, res)          -> the x-studio-key header must match env STUDIO_API_KEY
//                                     (constant-time). Fails closed with 503 when the env isn't set.

const crypto = require("crypto");

const ORIGINS = new Set([
  "https://studio.panicciventures.com",
  "https://panicci-content-engine.vercel.app",
  // This deployment's own URLs, so preview deployments keep working same-origin.
  process.env.VERCEL_URL && `https://${process.env.VERCEL_URL}`,
  process.env.VERCEL_BRANCH_URL && `https://${process.env.VERCEL_BRANCH_URL}`
].filter(Boolean));

function allowOrigin(req, res, headers) {
  const origin = req.headers.origin;
  res.setHeader("Vary", "Origin");
  if (origin && !ORIGINS.has(origin)) {
    res.status(403).json({ error: "origin_not_allowed", message: "This endpoint only serves the Panicci studio." });
    return false;
  }
  if (origin) res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", headers || "Content-Type");
  return true;
}

function studioKeyOk(req, res) {
  const want = process.env.STUDIO_API_KEY;
  if (!want) {
    res.status(503).json({
      error: "studio_key_not_configured",
      message: "STUDIO_API_KEY not configured. Add it in Vercel → Project → Settings → Environment Variables (same value as the studio key), then redeploy."
    });
    return false;
  }
  const got = String(req.headers["x-studio-key"] || "");
  // Hash both sides so the compare is constant-time and length-independent.
  const a = crypto.createHash("sha256").update(got).digest();
  const b = crypto.createHash("sha256").update(want).digest();
  if (!got || !crypto.timingSafeEqual(a, b)) {
    res.status(401).json({ error: "bad_studio_key", message: "Studio key missing or wrong. Paste it again from the OS." });
    return false;
  }
  return true;
}

module.exports = { allowOrigin, studioKeyOk, ORIGINS };
