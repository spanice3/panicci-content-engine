// Panicci Content Engine — Claude-powered teleprompter script writer.
// Runs as a Vercel serverless function. Holds the API key server-side so it is
// never exposed to the browser. POST { topic, tone, seconds, brandVoice, extra }.

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
// Overridable via env; "-latest" aliases track the current model automatically.
const MODEL = process.env.ANTHROPIC_MODEL || "claude-3-5-sonnet-latest";

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

  const topic = (body.topic || "").toString().slice(0, 600).trim();
  const tone = (body.tone || "").toString().slice(0, 120).trim();
  const brandVoice = (body.brandVoice || "").toString().slice(0, 600).trim();
  const extra = (body.extra || "").toString().slice(0, 600).trim();
  const seconds = Math.min(180, Math.max(15, parseInt(body.seconds, 10) || 60));

  if (!topic) { res.status(400).json({ error: "missing_topic", message: "Tell me the topic or idea to write a script about." }); return; }

  // Rough spoken-word budget: ~2.5 words per second of camera time.
  const targetWords = Math.round(seconds * 2.5);

  const system = [
    "You write short, punchy first-person scripts for a founder to read off a teleprompter and deliver straight to camera for social video (Instagram, TikTok, Facebook, LinkedIn).",
    "Write for the spoken word: plain, natural sentences, easy to read aloud, no tongue-twisters.",
    "Open with a scroll-stopping hook in the first line, deliver real value in the middle, and close with a clear call to action.",
    "Do NOT include stage directions, camera notes, speaker labels, headings, timestamps, markdown, or emojis — return only the words to be spoken.",
    "Use line breaks and blank lines deliberately as pacing: put each sentence or short phrase on its own line, and insert a blank line wherever the speaker should take a natural pause or breath. Longer pauses can use two blank lines. Preserve this whitespace exactly.",
    "Return STRICT JSON only — no prose, no code fences.",
    "In the JSON, encode every line break as \\n (so a blank-line pause is \\n\\n). Keep all intended spacing.",
    "Shape: {\"script\":\"First hook line.\\n\\nNext beat.\\n\\nThen the value.\"}"
  ].join("\n");

  const user = [
    `Topic / idea: ${topic}`,
    tone ? `Tone: ${tone}` : "",
    brandVoice ? `Brand voice to match: ${brandVoice}` : "",
    extra ? `Extra context / this week's angle: ${extra}` : "",
    `Target length: about ${seconds} seconds of spoken delivery (roughly ${targetWords} words).`,
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
        max_tokens: 1500,
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
    const script = parseScript(raw);

    if (!script) {
      res.status(502).json({ error: "parse_failed", message: "Claude returned an unexpected format.", raw: raw.slice(0, 500) });
      return;
    }
    res.status(200).json({ script, model: MODEL });
  } catch (err) {
    res.status(500).json({ error: "server_error", message: (err && err.message) || "unknown" });
  }
};

// Pull the {script:"..."} string out of Claude's reply, tolerating stray text/fences.
function parseScript(text) {
  if (!text) return "";
  let s = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  let obj = null;
  try { obj = JSON.parse(s); } catch (_) {
    const m = s.match(/\{[\s\S]*\}/);
    if (m) { try { obj = JSON.parse(m[0]); } catch (_) {} }
  }
  let out = "";
  if (obj && typeof obj.script === "string") out = obj.script;
  else if (obj && Array.isArray(obj.script)) out = obj.script.join("\n\n");
  else if (typeof obj === "string") out = obj;
  else out = s; // last resort: use the raw text if it wasn't JSON at all
  return out.replace(/\r\n/g, "\n").trim();
}
