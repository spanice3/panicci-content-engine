// Panicci Content Engine — shared-secret gate for the Claude-backed endpoints.
// Set CONTENT_ENGINE_TOKEN in Vercel (Project → Settings → Environment Variables).
// Callers send it as the "x-engine-token" header. Fails closed when unset.
// The leading underscore keeps Vercel from deploying this file as its own route.

const crypto = require("crypto");

function safeEqual(a, b) {
  const ab = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ab.length !== bb.length) return false;
  return crypto.timingSafeEqual(ab, bb);
}

// Returns true when the request may proceed; otherwise writes the response.
module.exports = function requireToken(req, res) {
  const expected = process.env.CONTENT_ENGINE_TOKEN;
  if (!expected) {
    res.status(503).json({
      error: "auth_not_configured",
      message: "CONTENT_ENGINE_TOKEN is not set in Vercel. Add it under Project → Settings → Environment Variables, then redeploy."
    });
    return false;
  }
  const got = req.headers["x-engine-token"] || "";
  if (!got || !safeEqual(got, expected)) {
    res.status(401).json({ error: "unauthorized", message: "Missing or wrong access token." });
    return false;
  }
  return true;
};
