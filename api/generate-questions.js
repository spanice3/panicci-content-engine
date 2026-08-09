// Panicci Content Engine — Claude-powered interview question generator.
// Runs as a Vercel serverless function. Holds the API key server-side so it is
// never exposed to the browser. POST { niche, count, types, brandVoice, extra }.
//
// Format-aware: every question is grounded in a specific proven format from
// lib/formats.js (not a generic "write a hot take" prompt) and, once the
// performance feedback loop has data for this niche, biased toward the formats
// that have actually driven views for it — see lib/performance-store.js.

const { forTypes, byId } = require("../lib/formats");
const { topFormatsForNiche } = require("../lib/performance-store");

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
// Overridable via env; "-latest" aliases track the current model automatically.
const MODEL = process.env.ANTHROPIC_MODEL || "claude-3-5-sonnet-latest";

const TYPE_GUIDE = {
  NICHE: "a specific, useful industry question the expert can answer with real value (no fluff).",
  HOT:   "a punchy, slightly spicy hot take tied to something trending or debated right now.",
  OU:    "a fast 'overrated or underrated?' prompt naming one specific thing.",
  INTRO: "a short warm intro prompt (who they are / who they help).",
  CTA:   "a natural closing prompt inviting the viewer to take the next step."
};

module.exports = async (req, res) => {
  // CORS (same-origin in prod; permissive so it also works if embedded).
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "Use POST" }); return; }

  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    res.status(503).json({
      error: "not_configured",
      message: "ANTHROPIC_API_KEY is not set in Vercel. Add it under Project → Settings → Environment Variables, then redeploy."
    });
    return;
  }

  // Body may arrive parsed (Vercel) or as a raw string.
  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};

  const niche = (body.niche || "").toString().slice(0, 400).trim();
  const brandVoice = (body.brandVoice || "").toString().slice(0, 600).trim();
  const extra = (body.extra || "").toString().slice(0, 600).trim();
  const count = Math.min(20, Math.max(1, parseInt(body.count, 10) || 8));
  const types = Array.isArray(body.types) && body.types.length
    ? body.types.filter((t) => TYPE_GUIDE[t])
    : ["INTRO", "NICHE", "NICHE", "NICHE", "HOT", "OU", "OU", "CTA"];

  if (!niche) { res.status(400).json({ error: "missing_niche", message: "Tell me the niche/industry to write questions for." }); return; }

  const typeList = types.join(", ");
  const guide = Object.entries(TYPE_GUIDE).map(([k, v]) => `- ${k}: ${v}`).join("\n");

  // Candidate formats: every format that fits at least one requested type.
  const candidates = forTypes(types);
  const formatCatalog = candidates
    .map((f) => `- ${f.id} (${f.name}, for ${f.bestTypes.join("/")}): ${f.whyItWorks}`)
    .join("\n");

  // If the studio's own posted-clip data shows winners for this niche, nudge toward them.
  let perfNote = "";
  try {
    const top = await topFormatsForNiche(niche, 5);
    if (top.length) {
      const named = top.map((t) => byId(t.formatId)).filter(Boolean);
      if (named.length) {
        perfNote = "\nThis studio's own posted-clip data shows these formats have driven the most views for THIS niche: "
          + named.map((f) => f.id).join(", ")
          + ". Prefer them when they're a natural fit — but don't force one that doesn't suit the question.";
      }
    }
  } catch (_) {
    // No performance data yet — proceed on format library alone.
  }

  const system = [
    "You write short, punchy on-camera interview questions for a founder to answer for social video (Instagram, TikTok, Facebook, LinkedIn).",
    "Each question must be answerable in 15–45 seconds and phrased for spoken delivery.",
    "Ground every question in ONE proven short-form format from the catalog below — do not invent questions unmoored from a format. Viral and high-authority content follows a small set of repeatable patterns; your job is to match the right pattern to this niche, not free-write.",
    "Format catalog:\n" + formatCatalog + perfNote,
    "Return STRICT JSON only — no prose, no code fences.",
    "Shape: {\"questions\":[{\"type\":\"NICHE\",\"format\":\"<format id from the catalog>\",\"text\":\"...\"}]}",
    "Allowed type values: NICHE, HOT, OU, INTRO, CTA.",
    "Type meanings:\n" + guide
  ].join("\n");

  const user = [
    `Niche / industry: ${niche}`,
    brandVoice ? `Brand voice to match: ${brandVoice}` : "",
    extra ? `Extra context / this week's angle: ${extra}` : "",
    `Produce exactly ${count} questions.`,
    `Use this ordered mix of types where possible: ${typeList}.`,
    "Make the HOT and OU ones genuinely scroll-stopping and current. Keep NICHE ones specific and value-first.",
    "Vary the formats used — don't lean on the same one or two formats for every question.",
    "Return the JSON object now."
  ].filter(Boolean).join("\n");

  try {
    const r = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 1800,
        system,
        messages: [{ role: "user", content: user }]
      })
    });

    if (!r.ok) {
      const detail = await r.text().catch(() => "");
      res.status(502).json({ error: "anthropic_error", status: r.status, message: detail.slice(0, 500) });
      return;
    }

    const data = await r.json();
    const raw = (data && data.content && data.content[0] && data.content[0].text) || "";
    const questions = parseQuestions(raw);

    if (!questions.length) {
      res.status(502).json({ error: "parse_failed", message: "Claude returned an unexpected format.", raw: raw.slice(0, 500) });
      return;
    }
    res.status(200).json({ questions, model: MODEL, count: questions.length });
  } catch (err) {
    res.status(500).json({ error: "server_error", message: (err && err.message) || "unknown" });
  }
};

// Pull the {questions:[...]} object out of Claude's reply, tolerating stray text/fences.
function parseQuestions(text) {
  if (!text) return [];
  let s = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/,"").trim();
  let obj = null;
  try { obj = JSON.parse(s); } catch (_) {
    const m = s.match(/\{[\s\S]*\}/);
    if (m) { try { obj = JSON.parse(m[0]); } catch (_) {} }
  }
  const arr = obj && Array.isArray(obj.questions) ? obj.questions : (Array.isArray(obj) ? obj : []);
  const ok = ["NICHE", "HOT", "OU", "INTRO", "CTA"];
  return arr
    .map((q) => {
      const format = byId((q.format || "").toString().trim());
      return {
        type: ok.includes((q.type || "").toString().toUpperCase()) ? q.type.toUpperCase() : "NICHE",
        text: (q.text || q.question || "").toString().trim(),
        format: format ? format.id : null,
        formatName: format ? format.name : null
      };
    })
    .filter((q) => q.text)
    .slice(0, 20);
}
