// Shared-secret auth for the Claude-backed API routes.
// Files prefixed with "_" in /api are NOT deployed as Vercel functions.
//
// Callers must send either:
//   Authorization: Bearer <CONTENT_ENGINE_API_TOKEN>
//   x-api-token: <CONTENT_ENGINE_API_TOKEN>
// The comparison is constant-time. If the env var is unset we fail closed (500).

const crypto = require("crypto");

function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-token");
}

function extractToken(req) {
  const h = req.headers || {};
  const auth = (h.authorization || h.Authorization || "").toString();
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (m) return m[1].trim();
  const x = (h["x-api-token"] || "").toString().trim();
  return x || "";
}

function safeEqual(a, b) {
  // Hash both sides so lengths match and timingSafeEqual never throws or leaks length.
  const ha = crypto.createHash("sha256").update(String(a), "utf8").digest();
  const hb = crypto.createHash("sha256").update(String(b), "utf8").digest();
  return crypto.timingSafeEqual(ha, hb);
}

// Returns true if the request may proceed; otherwise writes the response and returns false.
function requireApiToken(req, res) {
  const expected = process.env.CONTENT_ENGINE_API_TOKEN;
  if (!expected) {
    res.status(500).json({
      error: "auth_not_configured",
      message: "CONTENT_ENGINE_API_TOKEN is not set on the server. Add it in Vercel → Project → Settings → Environment Variables, then redeploy."
    });
    return false;
  }
  const provided = extractToken(req);
  if (!provided || !safeEqual(provided, expected)) {
    res.setHeader("WWW-Authenticate", 'Bearer realm="panicci-content-engine"');
    res.status(401).json({ error: "unauthorized", message: "Missing or invalid API token." });
    return false;
  }
  return true;
}

module.exports = { setCors, requireApiToken, extractToken, safeEqual };
