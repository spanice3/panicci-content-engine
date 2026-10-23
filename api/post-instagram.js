// Panicci Content Engine — hand a post to the OS social queue.
// This function never talks to Instagram and holds no IG token. It forwards to the panicci-os `studio-queue`
// edge function, which writes a public.social_queue row; the OS crons (ig-publish for stories/reels,
// social-publish for feed/carousels) publish it with the Vault tokens that ig-token-refresh keeps alive.
// Client accounts land in pending_approval and wait for Sammy in the OS; "panicci" posts go straight to queued.
//
// POST (x-studio-key required) one of:
//   { action: "accounts" }                                                -> IG accounts + whether each has a token
//   { account, kind: "reel"|"story"|"feed", mediaUrl, caption?, coverUrl?, scheduledAt? }
//   { account, kind: "carousel", mediaUrls: [2-10 urls], caption?, scheduledAt? }
//   { action: "status", id }                                              -> queue status, permalink once published
// Media must be reachable by Meta over public HTTPS (Vercel Blob URLs work).

const { allowOrigin, studioKeyOk } = require("./_lib/guard");

const QUEUE_FN = "https://sehnpskesbxgpdwknvvq.supabase.co/functions/v1/studio-queue";

module.exports = async (req, res) => {
  // Studio-only: locked to the studio origins and gated by the shared studio key.
  if (!allowOrigin(req, res, "Content-Type, x-studio-key")) return;
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "Use POST" }); return; }
  if (!studioKeyOk(req, res)) return;

  // Body may arrive parsed (Vercel) or as a raw string.
  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};

  const action = body.action === "accounts" || body.action === "status" ? body.action : "queue";
  const payload = {
    action,
    // studio-queue checks the same studio key against Vault
    key: String(req.headers["x-studio-key"] || ""),
    id: body.id,
    account: body.account,
    kind: body.kind,
    media_url: body.mediaUrl,
    media_urls: body.mediaUrls,
    caption: body.caption,
    cover_url: body.coverUrl,
    scheduled_at: body.scheduledAt
  };

  try {
    const r = await fetch(QUEUE_FN, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await r.json().catch(() => ({ error: `studio-queue ${r.status}` }));
    res.status(r.status).json(data);
  } catch (err) {
    res.status(502).json({ error: "queue_unreachable", message: (err && err.message) || "unknown" });
  }
};
