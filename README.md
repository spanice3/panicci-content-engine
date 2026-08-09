# Panicci Content Engine

Interview-style teleprompter + webcam recorder that turns one on-camera session into
platform-ready ad clips, with **Claude generating fresh interview questions on demand**.

Part of the Panicci Ventures Hub. Fully client-side recording; one tiny serverless
function proxies Claude so the API key never touches the browser.

## Structure
```
index.html                  # the app (teleprompter + recorder + interview mode)
lib/formats.js              # proven short-form format library (source of truth)
lib/performance-store.js    # Supabase REST client for the performance feedback loop
api/generate-questions.js   # serverless proxy → Anthropic Messages API, format-aware
api/formats.js              # serves the format library to the frontend
api/log-performance.js      # records a posted clip's real views against its format
api/format-leaderboard.js   # ranks formats by logged performance, per niche or studio-wide
supabase/migrations/        # schema for the format_performance table (panicci-hub project)
PLAYBOOK.md                 # how the format → shoot → log → improve loop works, and why
```

See `PLAYBOOK.md` for how the format library and performance loop actually work together.

## Deploy (Vercel)
1. Deploy this folder to Vercel (already done via the connector, or `vercel --prod`).
2. In **Project → Settings → Environment Variables**, add:
   - `ANTHROPIC_API_KEY` = your Anthropic API key (required)
   - `ANTHROPIC_MODEL` = optional, defaults to `claude-3-5-sonnet-latest`
   - `SUPABASE_URL` = the `panicci-hub` Supabase project URL (optional — enables the 📊 performance loop)
   - `SUPABASE_SERVICE_ROLE_KEY` = its service role key, server-side only (optional, same)
3. Redeploy so the new env vars take effect.

The API key is only ever read server-side in the function. It is never sent to the browser. Same for the Supabase service role key.

## Using it
- Open the site, switch to **🎙 Interview**.
- Click **✨ Generate with Claude**, enter your niche + this week's angle, pick a count.
- Questions auto-fill the builder. Edit, reorder, or add your own, then **Start interview**.
- While recording, tap **Next (N / →)** between questions — each jump marks a clean Q&A
  segment. Download the video + `.json` cut sheet and hand both to Claude to cut per platform.

## Cost
Question generation is a single short Claude call per click — pennies. Recording and
editing happen in the browser at no API cost.
