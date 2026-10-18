// Panicci Testimonial Studio — Vercel Blob client-upload endpoint.
// The browser uploads video straight to Blob storage; this function only mints
// a scoped upload token (client uploads dodge the 4.5MB serverless body limit).
// Requires the BLOB_READ_WRITE_TOKEN env var, added automatically when a Blob
// store is connected to this project in Vercel → Storage.

const fs = require("fs");
const path = require("path");
const { handleUpload } = require("@vercel/blob/client");
const { allowOrigin } = require("./_lib/guard");

const MAX_VIDEO_BYTES = 300 * 1024 * 1024; // 300 MB — one answer is 30-90 seconds
const MAX_META_BYTES = 1024 * 1024;        // 1 MB for the .meta.json sidecars
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
// testimonials/<slug>/<session stamp>-<name>/<q01-type.webm | q01-type.meta.json | session.meta.json>
const PATH_RE = /^testimonials\/([a-z0-9-]{1,60})\/[a-z0-9_-]{1,120}\/([a-z0-9_-]{1,40})\.(mp4|webm|mov|meta\.json)$/;

// Only studios that exist as clients/<slug>.json can receive uploads.
// (vercel.json includeFiles ships clients/ with this function.)
let slugs = null;
function knownSlugs() {
  if (!slugs) {
    slugs = new Set(fs.readdirSync(path.join(__dirname, "..", "clients"))
      .filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)));
  }
  return slugs;
}

module.exports = async (req, res) => {
  if (!allowOrigin(req, res)) return;
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "Use POST" }); return; }

  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    res.status(503).json({
      error: "not_configured",
      message: "BLOB_READ_WRITE_TOKEN is not set. In Vercel: Storage → Create Blob store → Connect to this project, then redeploy."
    });
    return;
  }

  // Body may arrive parsed (Vercel) or as a raw string.
  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = null; } }

  // Token requests come from the studio page, so they must carry a studio Origin (browsers always send
  // one on POST). The upload-completed callback comes from Vercel with no Origin and is signature-checked
  // by handleUpload.
  if (body && body.type === "blob.generate-client-token" && !req.headers.origin) {
    res.status(403).json({ error: "origin_not_allowed", message: "Uploads only work from the studio page." });
    return;
  }

  try {
    const jsonResponse = await handleUpload({
      body,
      request: req,

      onBeforeGenerateToken: async (pathname, clientPayload) => {
        // Every testimonial upload must identify who it came from.
        let payload = {};
        try { payload = JSON.parse(clientPayload || "{}"); } catch (_) {}
        const name = (payload.name || "").toString().trim();
        const email = (payload.email || "").toString().trim();
        if (name.length < 2 || !EMAIL_RE.test(email)) {
          throw new Error("A name and a valid email are required before uploading.");
        }
        const m = PATH_RE.exec(pathname || "");
        if (!m || !knownSlugs().has(m[1])) {
          throw new Error("That upload path isn't a Panicci testimonial studio.");
        }
        if (payload.clientSlug && payload.clientSlug !== m[1]) {
          throw new Error("Upload path doesn't match this studio.");
        }
        const isMeta = m[3] === "meta.json";
        return {
          allowedContentTypes: isMeta ? ["application/json"] : ["video/mp4", "video/webm", "video/quicktime"],
          maximumSizeInBytes: isMeta ? MAX_META_BYTES : MAX_VIDEO_BYTES,
          addRandomSuffix: true,
          // No name/email here: this payload comes back in the completion callback and its logs.
          tokenPayload: JSON.stringify({ slug: m[1], pathname })
        };
      },

      // Fires server-side once the blob has landed (not on localhost). Slug + path only, no PII.
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        let slug = "";
        try { slug = JSON.parse(tokenPayload || "{}").slug || ""; } catch (_) {}
        console.log("testimonial upload complete:", slug, blob.pathname);
      }
    });

    res.status(200).json(jsonResponse);
  } catch (err) {
    res.status(400).json({ error: "upload_error", message: (err && err.message) || "unknown" });
  }
};
