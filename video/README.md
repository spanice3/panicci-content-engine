# Panicci talking-head video pipeline

Turns raw teleprompter recordings into seamless, on-brand social videos:
cuts the teleprompter-wait pauses, removes flubbed retakes, adds Panicci
branding (animated open card, name lower-third, logo bug, burned-in captions,
animated closing card), and exports per platform with every overlay inside the
platform safe zones.

Three rules the editor keeps on its own (Sammy, Nov 11):

- **Never cover the face.** `face.py` finds Sammy's face every half second; the
  crop centres on it and every caption goes where it touches neither the face
  nor the lower third/bug (usual spot, else just under the beard, else above
  the head, shrinking the type if it has to).
- **Never cut a word early.** Cut ends come from the sound itself (`cutlib.Env`):
  a cut waits until the last word has stopped sounding (soft "s", trailing vowel),
  never reaching into the next word. Whisper alone ends words early: on the
  Nov 6 AZ take, 7 of 13 Whisper-timed cut points were still mid-word.
- **Open and close with life.** Both cards are a clean smiling shot of Sammy
  (`assets/sammy-smile.jpg`, both shoulders whole), a big hook and a play
  button. The open's first frame is the cover (also saved as
  `*_<ratio>_cover.png` for the Reels/Shorts cover): the gold word catches a
  sheen, the play button pulses, gets tapped, and the card irises open into the
  footage. The close collapses the footage back into the play button, rises the
  call to action in word by word and keeps the button pulsing. The words come
  from the script's first line (hook) and last line (call to action), or from a
  `cover` object in the Script data: `{"kicker", "hook", "emphasis",
  "closeKicker", "close", "closeEmphasis"}`.

This is a standalone tooling directory. It is not part of the Vercel deploy
(see `.vercelignore`).

## Setup (once per environment)

```bash
cd video && bash setup.sh
```

Installs a static `ffmpeg`, the Space Grotesk font (weighted + installed),
Python deps, and builds the brand assets into `video/.build/`.

**Cloud routines (Clipper, Reel Lab)** never run this themselves. The "Content Engine" cloud environment's setup
script clones this repo to `/opt/pce`, runs `setup.sh`, pre-downloads the Whisper model and writes
`/opt/pce/video/.ready` before Claude starts (log: `/var/log/pce-setup.log`). A routine only checks for `.ready`
and runs the scripts, so a run never clones, installs or downloads anything (that is what kept getting blocked).

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
- `--meta TAKE.json` reads the Script data (its `cover` words win over the script).
- `--hook "..."` overrides the big words on the open card; `--no-cards` skips both cards.

Outputs land in `--out-dir`: `seamless.mp4`, `captions.json`, and per format
one `*_<ratio>.mp4` plus its `*_<ratio>_cover.png`.

Preview the cards for a script without cutting anything:
`python3 opener.py script.txt ./covers 9x16,1x1`.

## 50·5·3 ads (`adbuild.py`)

For takes recorded in the studio's **🎯 50·5·3 Ads** tab. Download the take's MP4
and its **Script data (.json)** (after hitting *Find hooks · meats · CTAs*, so it
carries your picks), then:

```bash
python3 adbuild.py TAKE.mp4 --meta TAKE.json --out-dir ./ads          # Round 1 hook test
python3 adbuild.py TAKE.mp4 --meta TAKE.json --render all              # every combo
python3 adbuild.py TAKE.mp4 --meta TAKE.json --render clips            # modules only
python3 adbuild.py TAKE.mp4 --meta TAKE.json --brand 9x16,1x1          # + captions/bug
```

- Every module edge is snapped to Whisper word timestamps (the browser's are approximate).
- A **Ready 50·5·3 set** (`adsSet.meatsScripted`) needs no picks: every HOOK, MEAT and ADCTA segment is a module
  as read, in the set's order (the first meat and CTA lead round 1). No API call, no key.
- No adMatrix in the json otherwise? It transcribes and calls the studio's
  `/api/fifty-five-three` identify endpoint itself (same prompt as the browser).
  That call needs `STUDIO_API_KEY` in the environment (the studio key).
- Hooks/meats you dropped (✕) on the board are skipped.
- Output: `modules/H01.mp4 … M1.mp4 … C1.mp4`, one `H07-M1-C1.mp4` per ad,
  `ad-matrix.snapped.json`, and `manifest.csv`. Name each ad in Meta exactly as
  `ad_name` so the ad leaderboard maps straight back to hook/meat/CTA.
- `--brand` skips the intro card on purpose: an ad has to open on the hook.

## Frozen-take check (`avcheck.py`)

`run.py` and `adbuild.py` check every take first: if the picture freezes (a gap over 1.5 s between frames,
or the video ending 1.5 s+ before the sound, the iPhone failure from 2026-11-03), they stop with
`Frozen take, not cutting it: picture freezes at 0:12 while the sound runs to 1:43.` and cut nothing.
`--allow-frozen` overrides it when you want the audio anyway. Standalone:

```bash
python3 avcheck.py raw/*.mp4      # one line per take, exit 1 if any is frozen
```

## Drive I/O (`drive_io.py`)

Used by the OS Clipper Agent. Auth comes from the environment, never arguments:
`GDRIVE_ACCESS_TOKEN` (a 1-hour token; the agent mints one with
`select public.clipper_drive_token_start()` then `public.clipper_drive_token(<id>)`, so the
long-lived OAuth secrets never leave Supabase Vault), or `GDRIVE_CLIENT_ID` +
`GDRIVE_CLIENT_SECRET` + `GDRIVE_REFRESH_TOKEN` for local use.

```bash
python3 drive_io.py pull <shoot_folder_id> ./raw          # everything in <shoot>/raw
python3 drive_io.py push ./cuts <shoot_folder_id> --into cuts
```

Resumable uploads in 8 MB chunks, resuming from whatever Drive confirms it kept.

## Steps

1. **Silence jump-cut** — removes dead air; threshold auto-set ~12 dB below
   the take's mean level so quiet speech is preserved. Each kept stretch then
   runs until its last word has really finished and starts where its first
   word really begins.
2. **Retake collapse** (best-effort) — when a line is re-recorded within the
   same take, keeps the last clean pass and drops earlier attempts. It prints
   what it cut; review the result, and re-run with `--no-dedupe` if a real
   line was caught.
3. **Captions** — transcribes with `faster-whisper` (one pass serves the
   retake scan and the captions); with `--script`, aligns caption text to the
   script wording while timing comes from the audio. A line stays up until its
   last word is done.
4. **Brand** — `brandkit.py`, one ffmpeg pass: face-centred crop, lower-third,
   bug, captions placed off the face, then the open/close cards (`opener.py`,
   streamed in as lossless video with alpha) laid over the footage, with a soft
   tap and pop. Per-ratio safe-zone insets (9:16 tuned to TikTok: right action
   rail, top tabs, bottom caption/music/nav).

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
| `face.py` | finds the face (YuNet through onnxruntime, already installed with faster-whisper) |
| `opener.py` | animated open/close cards + cover still |
| `assets/face_detection_yunet_2023mar.onnx` | YuNet face detector, OpenCV Zoo, MIT, 230 KB |
| `assets/sammy-smile.jpg` | the smiling shot on every card (shoulders whole: see the repo CLAUDE.md photo law) |
| `run.py` | orchestrator |
| `adbuild.py` | 50·5·3 ad modules + combos |
| `clip_batch.py` | the Clipper's cut step: every take in a folder, two at a time, routed to `run.py` or `adbuild.py`, one JSON summary |
| `bjj_gjjw_v2.py` | Jiu-jitsu gym owner ads v2 (Brian's review, Nov 6): face on camera the whole time, title above the head, proof cards popping up above the head, no end card |
| `bjj_gjjw_ads.py` | Jiu-jitsu gym owner Meta ads (Nov 2026): on-camera hook, then voice-over proof scenes with real GJJW numbers and the AI answer screen recordings. Inputs in `ads/bjj-gjjw/` |
| `assets/brand-mark.svg` | the P/V shield |
