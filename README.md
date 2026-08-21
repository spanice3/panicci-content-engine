# Panicci Content Engine

Two tools on one Vercel project (`studio.panicciventures.com`):

1. **Teleprompter + recorder** (`/`) — Sammy's interview-style content rig with
   setting presets, eyeline mode, and Claude-powered question generation.
2. **Testimonial studios** (`/<client-slug>/`) — client-facing recording pages that
   capture **name + email**, walk the speaker through a personalized question set,
   and upload the video **directly to Vercel Blob** (no downloads, no email attachments).

## Structure
```
index.html                  # the teleprompter/recorder app (presets + eyeline)
testimonial.html            # ONE shared testimonial engine — config-driven
clients/<slug>.json         # per-client config: name, tagline, questions, editing brief
api/generate-questions.js   # serverless proxy → Anthropic Messages API
api/upload-testimonial.js   # mints scoped Vercel Blob client-upload tokens
vercel.json                 # cleanUrls + /:client → testimonial.html rewrite
```

## How testimonial pages work
`studio.panicciventures.com/gracie-jiu-jitsu-warwick` → the rewrite serves
`testimonial.html`, which reads the slug from the URL and fetches
`/clients/gracie-jiu-jitsu-warwick.json`. **Adding a client = adding one JSON file.**

Config schema (all optional except `name` + `questions`):
```json
{
  "name": "Business Name",            // header + metadata
  "shortName": "BIZ",                 // filename prefix for takes
  "tagline": "Share Your Story — Video Testimonial",
  "accent": "#4f8cff",                // theme color override
  "introHtml": "<b>Thanks!</b> …",    // welcome copy (trusted, repo-authored)
  "questions": [{ "type": "INTRO", "label": "Intro", "text": "…" }],
  "editingBrief": "…"                 // instructions embedded in the cut-sheet JSON
}
```

### Current studios
- `/gracie-jiu-jitsu-warwick` — GJJW **customer** testimonials (members' stories)
- `/pv-gracie-jiu-jitsu-warwick`, `/pv-desert-dog`, `/pv-rogue-island`,
  `/pv-chicali-tacos`, `/pv-thirsty-pirate`, `/pv-headcase`, `/pv-roadworthy` —
  **Panicci Ventures partner** testimonials, personalized with each client's real
  GSC/ranking/review stats (pulled Aug 2026 — refresh before re-sending links)
- `/partner` — generic PV partner testimonial for clients without a custom page yet

## Recording → Blob flow
1. Client enters name + email (required — Start is gated on it).
2. Records takes with the eyeline cue-card flow; each Next-press marks a Q&A segment.
3. **📤 Send my video** uploads the take straight from the browser to Vercel Blob
   (client upload — no serverless body limit; multipart for big files), plus a
   `.meta.json` cut sheet: person, questions, segment in/out points, editing brief.
4. Files land at `testimonials/<client-slug>/<date>-<person>/take-N.*` with a
   random suffix. Browse them in Vercel → Storage → Blob.

`api/upload-testimonial.js` refuses tokens without a valid name + email and only
allows the `testimonials/` prefix. Note: Blob URLs are public-but-unguessable, and
the `.meta.json` includes the person's email — don't share meta URLs.

## Deploy (Vercel)
Push to `main` → auto-deploys to `studio.panicciventures.com`.

Environment (Project → Settings → Environment Variables):
- `ANTHROPIC_API_KEY` — required for question generation (`ANTHROPIC_MODEL` optional)
- `BLOB_READ_WRITE_TOKEN` — **added automatically** when you connect a Blob store:
  **Vercel → Storage → Create Database → Blob → connect to `panicci-content-engine`**,
  then redeploy. Until then the send button shows a friendly "not switched on yet"
  message and clients can still download their video.

## Cost
Recording is fully client-side. Question generation is pennies per click.
Blob: ~$0.023/GB-month storage + egress on download — testimonial volumes are noise.
