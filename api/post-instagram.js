// Panicci Content Engine — publish to Instagram via the Graph API (content publishing).
// Runs as a Vercel serverless function so the IG token stays server-side.
//
// Env:
//   IG_ACCESS_TOKEN   long-lived token. "IGAA…" tokens (Instagram Login) hit graph.instagram.com;
//                     anything else (Facebook Login / Page token) hits graph.facebook.com.
//   IG_USER_ID        IG professional account id. Optional for IGAA tokens (defaults to "me"),
//                     required for Facebook Login tokens.
//   IG_GRAPH_VERSION  optional, default v23.0.
//
// POST (x-studio-key required) one of:
//   { action: "check" }                                            -> which account the token posts as
//   { type: "image", mediaUrl, caption }                           -> feed photo (JPEG, public URL)
//   { type: "reel",  mediaUrl, caption, shareToFeed?, coverUrl? }  -> Reel (MP4/MOV, public URL)
//   { type: "carousel", items: [{ type: "image"|"video", mediaUrl }], caption }  -> 2-10 items
//   { containerId }                                                -> retry publishing a container
//                                                                     that was still processing
// Media must be reachable by Meta over public HTTPS (Vercel Blob URLs work).

const { allowOrigin, studioKeyOk } = require("./_lib/guard");

const VERSION = process.env.IG_GRAPH_VERSION || "v23.0";
const POLL_MS = 3000;
const POLL_BUDGET_MS = 50 * 1000; // leave headroom under the 60s maxDuration

function apiBase(token) {
  const host = token.startsWith("IGAA") ? "graph.instagram.com" : "graph.facebook.com";
  return `https://${host}/${VERSION}`;
}

async function graph(base, token, method, path, params) {
  const qs = new URLSearchParams({ ...(params || {}), access_token: token });
  const url = method === "GET" ? `${base}/${path}?${qs}` : `${base}/${path}`;
  const r = await fetch(url, method === "GET" ? {} : {
    method,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: qs
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok || data.error) {
    const e = data.error || {};
    const err = new Error(e.error_user_msg || e.message || `Graph API ${r.status}`);
    err.status = r.status;
    err.code = e.code;
    throw err;
  }
  return data;
}

// Video containers process async; images are usually FINISHED immediately.
async function waitForContainer(base, token, id) {
  const start = Date.now();
  for (;;) {
    const { status_code: s, status } = await graph(base, token, "GET", id, { fields: "status_code,status" });
    if (s === "FINISHED" || s === "PUBLISHED") return "ready";
    if (s === "ERROR" || s === "EXPIRED") throw Object.assign(new Error(`Container ${s}: ${status || "no detail"}`), { status: 422 });
    if (Date.now() - start > POLL_BUDGET_MS) return "processing";
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

async function publish(base, token, igUser, containerId) {
  const state = await waitForContainer(base, token, containerId);
  if (state === "processing") return { status: "processing", containerId };
  const { id } = await graph(base, token, "POST", `${igUser}/media_publish`, { creation_id: containerId });
  const { permalink } = await graph(base, token, "GET", id, { fields: "permalink" }).catch(() => ({}));
  return { status: "published", mediaId: id, permalink: permalink || null };
}

const isUrl = (u) => typeof u === "string" && /^https:\/\/\S+$/.test(u);

module.exports = async (req, res) => {
  // Studio-only: locked to the studio origins and gated by the shared studio key.
  if (!allowOrigin(req, res, "Content-Type, x-studio-key")) return;
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "Use POST" }); return; }
  if (!studioKeyOk(req, res)) return;

  const token = process.env.IG_ACCESS_TOKEN;
  if (!token) {
    res.status(503).json({
      error: "not_configured",
      message: "IG_ACCESS_TOKEN is not set in Vercel. Add it under Project → Settings → Environment Variables, then redeploy."
    });
    return;
  }
  const base = apiBase(token);
  const igUser = process.env.IG_USER_ID || (token.startsWith("IGAA") ? "me" : "");
  if (!igUser) {
    res.status(503).json({
      error: "not_configured",
      message: "IG_USER_ID is required with a Facebook Login token. Add the Instagram professional account id in Vercel, then redeploy."
    });
    return;
  }

  // Body may arrive parsed (Vercel) or as a raw string.
  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};

  const caption = (body.caption || "").toString().slice(0, 2200);

  try {
    if (body.action === "check") {
      const me = await graph(base, token, "GET", igUser, { fields: "id,username" });
      const limit = await graph(base, token, "GET", `${me.id}/content_publishing_limit`, { fields: "quota_usage,config" })
        .then((d) => (d.data && d.data[0]) || null).catch(() => null);
      res.status(200).json({ ok: true, id: me.id, username: me.username, publishingLimit: limit });
      return;
    }

    if (body.containerId) {
      if (!/^\d+$/.test(String(body.containerId))) { res.status(400).json({ error: "bad_container_id" }); return; }
      res.status(200).json(await publish(base, token, igUser, String(body.containerId)));
      return;
    }

    let container;
    if (body.type === "image") {
      if (!isUrl(body.mediaUrl)) { res.status(400).json({ error: "missing_media_url", message: "Send a public https mediaUrl (JPEG)." }); return; }
      container = await graph(base, token, "POST", `${igUser}/media`, { image_url: body.mediaUrl, caption });
    } else if (body.type === "reel") {
      if (!isUrl(body.mediaUrl)) { res.status(400).json({ error: "missing_media_url", message: "Send a public https mediaUrl (MP4/MOV)." }); return; }
      const params = { media_type: "REELS", video_url: body.mediaUrl, caption, share_to_feed: body.shareToFeed === false ? "false" : "true" };
      if (isUrl(body.coverUrl)) params.cover_url = body.coverUrl;
      container = await graph(base, token, "POST", `${igUser}/media`, params);
    } else if (body.type === "carousel") {
      const items = Array.isArray(body.items) ? body.items : [];
      if (items.length < 2 || items.length > 10 || !items.every((i) => i && isUrl(i.mediaUrl))) {
        res.status(400).json({ error: "bad_items", message: "A carousel needs 2-10 items, each with a public https mediaUrl." });
        return;
      }
      const children = [];
      for (const i of items) {
        const p = i.type === "video"
          ? { media_type: "VIDEO", video_url: i.mediaUrl, is_carousel_item: "true" }
          : { image_url: i.mediaUrl, is_carousel_item: "true" };
        const { id } = await graph(base, token, "POST", `${igUser}/media`, p);
        if (await waitForContainer(base, token, id) === "processing") {
          res.status(504).json({ error: "child_processing", message: "A carousel video is still processing. Try again in a minute." });
          return;
        }
        children.push(id);
      }
      container = await graph(base, token, "POST", `${igUser}/media`, { media_type: "CAROUSEL", children: children.join(","), caption });
    } else {
      res.status(400).json({ error: "bad_type", message: 'type must be "image", "reel" or "carousel" (or action "check").' });
      return;
    }

    // "processing" means the Reel is still encoding — POST { containerId } again in a minute to finish.
    res.status(200).json(await publish(base, token, igUser, container.id));
  } catch (err) {
    const status = err.code === 190 ? 401 : (err.status >= 400 && err.status < 600 ? err.status : 502);
    res.status(status).json({
      error: err.code === 190 ? "ig_token_invalid" : "ig_error",
      message: err.code === 190 ? "Instagram token is expired or revoked. Generate a new long-lived token and update IG_ACCESS_TOKEN." : err.message
    });
  }
};
