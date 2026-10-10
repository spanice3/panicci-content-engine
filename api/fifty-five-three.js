// Panicci Content Engine — Hormozi 50·5·3 ad builder.
// One Vercel serverless function, two actions:
//
//   POST { action: "plan", offer, audience, proof, cta, voice, counts }
//     -> a shoot list: interview questions that pull out "meats" (stories, proof,
//        how-it-works, objection kills), N hook lines to read, and CTA lines to read.
//
//   POST { action: "identify", segments: [{n, type, prompt, start, end, transcript}], counts }
//     -> what actually landed on camera: ranked hooks, the best meats (with start/end
//        quotes so the editor can cut them), the CTAs, and anything worth a reshoot.
//
// The browser studio (index.html, 50·5·3 tab) and video/adbuild.py both call this,
// so there's one prompt, not two drifting copies.

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5-5";

const HOOK_STYLES = ["callout", "question", "bold-claim", "proof", "contrarian", "story", "curiosity", "list", "negative", "if-then"];
const MEAT_ANGLES = ["story", "proof", "demo", "education", "objection"];

module.exports = async (req, res) => {
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

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};

  const counts = clampCounts(body.counts);
  const voice = str(body.voice, 600) ||
    "Warm, confident, plain English. Contractions. Talks like texting a smart friend. Backs claims with real numbers. No corporate jargon, no hype.";

  let built;
  if (body.action === "plan") built = buildPlan(body, counts, voice);
  else if (body.action === "identify") built = buildIdentify(body, counts);
  else { res.status(400).json({ error: "bad_action", message: "action must be \"plan\" or \"identify\"." }); return; }
  if (built.error) { res.status(400).json(built); return; }

  try {
    const r = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 8000,
        system: built.system,
        messages: [{ role: "user", content: built.user }]
      })
    });
    if (!r.ok) {
      const detail = await r.text().catch(() => "");
      res.status(502).json({ error: "anthropic_error", status: r.status, message: detail.slice(0, 500) });
      return;
    }
    const data = await r.json();
    const raw = (data && data.content || []).filter((c) => c.type === "text").map((c) => c.text).join("");
    const obj = parseJson(raw);
    if (!obj) { res.status(502).json({ error: "parse_failed", message: "Claude returned an unexpected format.", raw: raw.slice(0, 500) }); return; }
    const out = body.action === "plan" ? cleanPlan(obj, counts) : cleanIdentify(obj, built.segIds);
    res.status(200).json({ ...out, counts, model: MODEL });
  } catch (err) {
    res.status(500).json({ error: "server_error", message: (err && err.message) || "unknown" });
  }
};

// ---------- plan ----------
function buildPlan(body, counts, voice) {
  const offer = str(body.offer, 800);
  if (!offer) return { error: "missing_offer", message: "Tell me the offer you're running ads for." };
  const audience = str(body.audience, 600);
  const proof = str(body.proof, 1200);
  const cta = str(body.cta, 400);
  const nQ = Math.min(14, counts.meats * 2);

  const system = [
    "You are a direct-response video ad strategist running Alex Hormozi's hook / meat / CTA modular ad process.",
    "An ad = HOOK (first 3-5 seconds, earns attention) + MEAT (15-60 seconds, earns belief) + CTA (5-10 seconds, earns the click).",
    "Hooks, meats and CTAs are filmed as separate modules so every hook can be stitched onto every meat and every CTA.",
    "The founder films three blocks in one session:",
    "1) INTERVIEW: you ask questions, they answer off the cuff. Their answers become the MEATS. Ask questions that pull out a specific story, hard proof with numbers, how the offer actually works (demo), a teaching moment, and the top objection killed. Questions must invite a 30-60 second answer that stands alone without the question being heard.",
    "2) HOOKS: lines they read straight to camera. Each hook must work in front of ANY meat, so no hook may depend on a specific story detail. Max 18 words, one breath. Lead with a callout of the audience or a specific result. Vary the style across: " + HOOK_STYLES.join(", ") + ".",
    "3) CTAS: lines they read to close. Each says exactly what to do next and why now, max 25 words, no fake scarcity.",
    "Write everything for the spoken word in this voice: " + voice,
    "Never invent results, client names or numbers that are not in the proof given. If proof is thin, write hooks that don't need numbers.",
    "Return STRICT JSON only, no prose, no code fences.",
    "Shape: {\"interview\":[{\"text\":\"question\",\"angle\":\"story|proof|demo|education|objection\"}],\"hooks\":[{\"text\":\"line\",\"style\":\"callout\"}],\"ctas\":[{\"text\":\"line\"}]}"
  ].join("\n");

  const user = [
    `Offer: ${offer}`,
    audience ? `Who it's for: ${audience}` : "",
    proof ? `Real proof / results / story material: ${proof}` : "Real proof: none given.",
    cta ? `Where the CTA sends people: ${cta}` : "",
    `Produce exactly ${nQ} interview questions (spread across the angles), ${counts.hooks} hooks, and ${counts.ctas} CTAs.`,
    "Return the JSON object now."
  ].filter(Boolean).join("\n");
  return { system, user };
}

function cleanPlan(obj, counts) {
  const interview = arr(obj.interview).map((q) => ({
    text: str(q.text || q.question, 400),
    angle: MEAT_ANGLES.includes(q.angle) ? q.angle : "story"
  })).filter((q) => q.text).slice(0, 20);
  const hooks = dedupe(arr(obj.hooks).map((h) => ({
    text: str(typeof h === "string" ? h : h.text, 300),
    style: HOOK_STYLES.includes(h.style) ? h.style : "callout"
  })).filter((h) => h.text)).slice(0, counts.hooks);
  const ctas = arr(obj.ctas).map((c) => ({ text: str(typeof c === "string" ? c : c.text, 300) }))
    .filter((c) => c.text).slice(0, counts.ctas);
  return { interview, hooks, ctas };
}

// ---------- identify ----------
function buildIdentify(body, counts) {
  const segs = arr(body.segments).slice(0, 150).map((s) => ({
    n: parseInt(s.n, 10),
    type: str(s.type, 12).toUpperCase(),
    prompt: str(s.prompt || s.question, 400),
    start: num(s.start), end: num(s.end),
    transcript: str(s.transcript, 6000)
  })).filter((s) => Number.isFinite(s.n));
  if (!segs.length) return { error: "missing_segments", message: "No recorded segments to analyze." };
  if (!segs.some((s) => s.transcript)) {
    return { error: "no_transcript", message: "No transcript came through for this take. Use Chrome with Live transcript on, or run video/adbuild.py (Whisper) on the downloaded take." };
  }

  const system = [
    "You are a direct-response video editor running Alex Hormozi's hook / meat / CTA modular ad process.",
    "You get a founder's filmed session, split into segments. Each segment has a type:",
    "- MEAT: an interview answer to the prompt shown. Find the meats here.",
    "- HOOK: the founder read the prompt line as a hook. The transcript is what they actually said.",
    "- ADCTA: the founder read the prompt line as a call to action.",
    "Your job: identify every usable module and rank it.",
    `HOOKS (target up to ${counts.hooks}): every HOOK segment that was delivered cleanly, PLUS any punchy standalone line buried in an interview answer that would stop a scroll (source "interview"). A hook must make sense with zero context, run under ~6 seconds, and work in front of any meat. Use the words as actually spoken, not the script. If a HOOK segment has no transcript, assume it was read as scripted and say so in "why".`,
    `MEATS (pick the best ${counts.meats}): a continuous 15-60 second stretch of one interview answer that stands alone without the question, earns belief (story, proof with numbers, how it works, teaching, objection killed), and contains no greeting and no CTA. Give the exact first words (startQuote) and last words (endQuote) of the stretch, 5-10 words each, copied verbatim from the transcript so an editor can find the cut points.`,
    `CTAS (best ${counts.ctas}): from ADCTA segments, or a clean natural close inside an answer.`,
    "RESHOOT: list HOOK or ADCTA segments that were flubbed, trailed off, or drifted badly from the script, with a short reason.",
    "Score each module 1-10 for how hard it would perform in a paid social ad (10 = would bet budget on it). Sort each list best first.",
    "Return STRICT JSON only, no prose, no code fences.",
    "Shape: {\"hooks\":[{\"seg\":3,\"text\":\"exact spoken words\",\"style\":\"" + HOOK_STYLES.join("|") + "\",\"score\":8,\"source\":\"read|interview\",\"why\":\"short\"}],",
    "\"meats\":[{\"seg\":1,\"title\":\"3-6 word label\",\"angle\":\"" + MEAT_ANGLES.join("|") + "\",\"startQuote\":\"...\",\"endQuote\":\"...\",\"score\":9,\"why\":\"short\"}],",
    "\"ctas\":[{\"seg\":40,\"text\":\"exact spoken words\",\"score\":7,\"why\":\"short\"}],",
    "\"reshoot\":[{\"seg\":12,\"reason\":\"short\"}]}"
  ].join("\n");

  const lines = segs.map((s) =>
    `--- SEGMENT ${s.n} · ${s.type} · ${fmt(s.start)}-${fmt(s.end)}\nPROMPT: ${s.prompt || "(none)"}\nTRANSCRIPT: ${s.transcript || "(missing)"}`
  );
  const user = lines.join("\n\n") + "\n\nReturn the JSON object now.";
  return { system, user, segIds: new Set(segs.map((s) => s.n)) };
}

function cleanIdentify(obj, segIds) {
  const okSeg = (x) => segIds.has(parseInt(x, 10));
  const score = (x) => Math.max(1, Math.min(10, parseInt(x, 10) || 5));
  const byScore = (a, b) => b.score - a.score;
  const hooks = arr(obj.hooks).filter((h) => okSeg(h.seg) && str(h.text, 300)).map((h) => ({
    seg: parseInt(h.seg, 10), text: str(h.text, 300),
    style: HOOK_STYLES.includes(h.style) ? h.style : "callout",
    score: score(h.score), source: h.source === "interview" ? "interview" : "read", why: str(h.why, 200)
  })).sort(byScore);
  const meats = arr(obj.meats).filter((m) => okSeg(m.seg) && str(m.startQuote, 200)).map((m) => ({
    seg: parseInt(m.seg, 10), title: str(m.title, 80) || "Meat",
    angle: MEAT_ANGLES.includes(m.angle) ? m.angle : "story",
    startQuote: str(m.startQuote, 200), endQuote: str(m.endQuote, 200),
    score: score(m.score), why: str(m.why, 200)
  })).sort(byScore);
  const ctas = arr(obj.ctas).filter((c) => okSeg(c.seg) && str(c.text, 300)).map((c) => ({
    seg: parseInt(c.seg, 10), text: str(c.text, 300), score: score(c.score), why: str(c.why, 200)
  })).sort(byScore);
  const reshoot = arr(obj.reshoot).filter((r) => okSeg(r.seg)).map((r) => ({ seg: parseInt(r.seg, 10), reason: str(r.reason, 200) }));
  return { hooks, meats, ctas, reshoot };
}

// ---------- helpers ----------
function clampCounts(c) {
  c = c || {};
  const n = (v, d, lo, hi) => Math.min(hi, Math.max(lo, parseInt(v, 10) || d));
  return { hooks: n(c.hooks, 50, 5, 60), meats: n(c.meats, 5, 1, 8), ctas: n(c.ctas, 3, 1, 5) };
}
function str(v, max) { return (v == null ? "" : String(v)).slice(0, max).trim(); }
function num(v) { const x = Number(v); return Number.isFinite(x) ? x : null; }
function arr(v) { return Array.isArray(v) ? v : []; }
function fmt(t) { return t == null ? "?" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`; }
function dedupe(list) {
  const seen = new Set();
  return list.filter((x) => { const k = x.text.toLowerCase().replace(/[^a-z0-9]/g, ""); if (seen.has(k)) return false; seen.add(k); return true; });
}
function parseJson(text) {
  if (!text) return null;
  const s = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  try { return JSON.parse(s); } catch (_) {}
  const m = s.match(/\{[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch (_) {} }
  return null;
}

module.exports._test = { cleanPlan, cleanIdentify, buildIdentify, buildPlan, clampCounts, parseJson };
