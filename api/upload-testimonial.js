// Panicci Testimonial Studio — Vercel Blob client-upload endpoint.
// The browser uploads video straight to Blob storage; this function only mints
// a scoped upload token (client uploads dodge the 4.5MB serverless body limit).
// Requires the BLOB_READ_WRITE_TOKEN env var, added automatically when a Blob
// store is connected to this project in Vercel → Storage.

const { handleUpload } = require("@vercel/blob/client");

const MAX_BYTES = 1024 * 1024 * 1024; // 1 GB per file — plenty for a long take
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
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
        if (!/^testimonials\//.test(pathname)) {
          throw new Error("Uploads must live under testimonials/.");
        }
        return {
          allowedContentTypes: ["video/mp4", "video/webm", "video/quicktime", "application/json"],
          maximumSizeInBytes: MAX_BYTES,
          addRandomSuffix: true,
          tokenPayload: JSON.stringify({ name, email, pathname, client: payload.client || "", take: payload.take || null })
        };
      },

      // Fires server-side once the blob has landed (not on localhost).
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        console.log("testimonial upload complete:", blob.pathname, tokenPayload);
      }
    });

    res.status(200).json(jsonResponse);
  } catch (err) {
    res.status(400).json({ error: "upload_error", message: (err && err.message) || "unknown" });
  }
};
