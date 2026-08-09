# Studio Playbook — Format-Matched Content Engine

What used to be "ask Claude for some interview questions" is now a closed loop:
**pick a proven format → shoot it live in one session → cut per platform → log
what it actually did → let that data sharpen the next shoot.** This doc is the
human-readable map of that loop. The code is the source of truth — this is the
"why," not a spec.

## 1. How a shoot works now

1. Open the app, switch to 🎙 Interview, click **✨ Generate with Claude**.
2. Claude no longer free-writes questions — every question it returns is built
   on one specific format from `lib/formats.js` (`api/generate-questions.js`
   grounds the prompt in the format catalog and requires a format citation per
   question). You'll see the format name as a small tag under each question.
3. While filming, the cue card shows which format you're filming
   ("▸ Filming: The Objection Flip") — the talent/interviewer knows the shape
   of the answer being asked for, not just the topic.
4. Recording exports a `.json` cut sheet where every segment carries its
   `format` and `formatName`. The editing brief tells Claude (or a human
   editor) to cut in that format's spirit — hold the reveal on Hook-Reveal
   formats, keep the cold open pure on Storytelling formats, etc.
5. A few days after a clip is posted, log its views (and watch-through % if
   you have it) in the **📊** panel. That's the entire manual step — one
   number, tied to the format and niche it came from.
6. Next time you generate questions for that niche, `api/generate-questions.js`
   checks `format_performance` first and nudges toward whatever's actually
   worked there before — see `topFormatsForNiche()` in
   `lib/performance-store.js`.

That's the full loop: **format library → live generation → shoot → cut → log →
better generation.** Nothing about it requires leaving this app.

## 2. The format library

Full library with structure, "why it works," and hook templates lives in
[`lib/formats.js`](./lib/formats.js) — treat that file as canonical, not this
table (this list will drift; the code won't). Two families:

**Consumer / viral-creator patterns** — the well-documented shapes any
format-matching tool draws on: Personal Story, Would You Rather, Myth Bust,
Blind Test, Expensive Secret Reveal, First vs Pro, Quiz With Consequences,
Before/After, Hot Take, Behind the Build.

**Authority formats (Panicci's own addition)** — built specifically for
interview-style, on-camera expert/founder content: Founder Origin Story,
Client Result Reveal, Myth vs Reality, AMA Rapid Fire, The Objection Flip,
The Expensive Mistake, Numbers Don't Lie, Overrated/Underrated (Industry
Edition), The Direct Next Step.

Add a new format by appending an object to the `FORMATS` array — no other file
needs to change; `api/formats.js`, `api/generate-questions.js`, and the
frontend all read from it live.

## 3. Why this beats a generic format-matching SaaS

Every viral-format tool on the market (Format Finder included) is built for a
solo creator picking their own niche. That shapes what they're good at and
where they can't follow an agency:

| | Generic format-matcher (e.g. Format Finder) | Panicci Content Engine |
|---|---|---|
| **Format selection** | Separate research step before you ever pick up a camera | Happens live, in the same session, on the cue card |
| **Output per shoot** | One idea → one video, repeat | One session → a full segmented cut sheet, per platform |
| **Format coverage** | Skews consumer/lifestyle (cooking, tattoo art, fitness) | Covers that *and* founder/expert-authority formats built for service businesses — a category solo-creator tools don't serve well |
| **Performance data** | Locked inside their SaaS, benefits every subscriber equally (including competitors) | Lives in our own Supabase (`panicci-hub`), compounding privately across every client we shoot for |
| **Who gets smarter** | The vendor's whole user base at once | Only us — and only for the niches we actually work in |

That last row is the actual moat: **the format-performance table in
`panicci-hub` gets more accurate with every client we shoot, and nobody
outside Panicci can see or use it.** A single-creator tool can only ever learn
from one account's results. An agency running this across a dozen clients in a
dozen niches builds a dataset a solo tool structurally cannot — as long as we
actually log results every time (step 5 above is not optional if you want the
moat to be real instead of theoretical).

## 4. One-time setup

In Vercel → Project → Settings → Environment Variables:

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Already required — question generation |
| `ANTHROPIC_MODEL` | Optional override, defaults to `claude-3-5-sonnet-latest` |
| `SUPABASE_URL` | `panicci-hub` project API URL (Supabase dashboard → Project Settings → API) |
| `SUPABASE_SERVICE_ROLE_KEY` | Same page, **service role** key — server-side only, never exposed to the browser (read server-side in `lib/performance-store.js`, same pattern as the Anthropic key) |

The `format_performance` table already exists in `panicci-hub`
(`supabase/migrations/0001_format_performance.sql`). Until the Supabase env
vars are set, the app still works end-to-end — generation and recording don't
depend on them, and the 📊 panel just tells you it's "not connected yet"
instead of erroring.

## 5. What's next (not built yet, in priority order)

1. **Auto-pull views instead of manual logging.** Supermetrics MCP already has
   Instagram/TikTok/YouTube connectors available to this account — a scheduled
   job could pull views for posted clips automatically instead of relying on
   someone remembering to open the 📊 panel. Manual logging was the right MVP
   (zero new integrations, works today); this is the obvious next lift once
   the loop proves itself out.
2. **Per-client leaderboard view.** `/api/format-leaderboard` already accepts
   a niche filter — a client-facing report ("here's what's working in your
   vertical") is a thin layer on top and doubles as a retention/upsell asset.
3. **Expand the authority-format set from real data**, not guesses — once
   enough clips are logged, the formats with `postCount` still at 0 after a
   few months of shoots in a niche are candidates to prune or rewrite.
4. **One-click cut automation.** The editing brief in the exported `.json` is
   already format-aware; the next step is having Claude (or an ffmpeg pass)
   act on it directly instead of a human reading the brief and cutting by
   hand.
