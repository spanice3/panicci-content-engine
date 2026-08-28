# Panicci talking-head video pipeline

Turns raw teleprompter recordings into seamless, on-brand social videos:
cuts the teleprompter-wait pauses, removes flubbed retakes, adds Panicci
branding (intro card, name lower-third, logo bug, burned-in captions, outro
CTA), and exports per platform with every overlay inside the platform safe
zones.

This is a standalone tooling directory. It is not part of the Vercel deploy
(see `.vercelignore`).

## Setup (once per environment)

```bash
cd video && bash setup.sh
```

Installs a static `ffmpeg`, the Space Grotesk font (weighted + installed),
Python deps, and builds the brand assets into `video/.build/`.

## Run

```bash
python3 run.py TAKE.mp4 [MORE_TAKES.mp4 ...] \
    --script script.txt \
    --formats 9x16,1x1 \
    --out-dir ./out
```

- One take = it gets cut and branded. Multiple takes = each is cut, then
  concatenated in order (use for complementary halves of one script).
- `--script script.txt` makes caption wording exact (brand terms, spelling).
  Strip the teleprompter pause markers first: the recorder writes `\n|` lines
  as pause beats; keep only the spoken sentences.
- `--formats` any of `9x16` (Reels/TikTok/Shorts), `1x1` (feed), `16x9`
  (YouTube/LinkedIn).
- `--no-dedupe` skips the retake-collapse step.

Outputs land in `--out-dir`: `seamless.mp4`, `captions.json`, and one
`*_<ratio>.mp4` per format.

## Steps

1. **Silence jump-cut** — removes dead air; threshold auto-set ~12 dB below
   the take's mean level so quiet speech is preserved.
2. **Retake collapse** (best-effort) — when a line is re-recorded within the
   same take, keeps the last clean pass and drops earlier attempts. It prints
   what it cut; review the result, and re-run with `--no-dedupe` if a real
   line was caught.
3. **Captions** — transcribes with `faster-whisper`; with `--script`, aligns
   caption text to the script wording while timing comes from the audio.
4. **Brand** — `brandkit.py` composites the cards, lower-third, bug, and
   captions, with per-ratio safe-zone insets (9:16 tuned to TikTok: right
   action rail, top tabs, bottom caption/music/nav).

## Brand system

Sourced from the `panicci-deliverables` skill (`brand.json`): deep green
`#194324`, brand green `#296037`, gold `#ce9e27`, cream `#f9f6f1`, ink
`#12211a`, sage `#9bbfa1`; Space Grotesk; the interlocking P/V shield
(`assets/brand-mark.svg`). No em dashes, no AI slop.

## Files

| file | role |
|------|------|
| `setup.sh` | install ffmpeg + fonts + deps, build assets |
| `assets_build.py` | rasterize the mark, instantiate font weights |
| `cutlib.py` | silence detection, jump-cut, retake detection |
| `captions.py` | transcription + script alignment |
| `brandkit.py` | safe-zone branded renderer (importable + CLI) |
| `run.py` | orchestrator |
| `assets/brand-mark.svg` | the P/V shield |
