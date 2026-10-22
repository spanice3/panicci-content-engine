# HyperFrames video templates

Promo and proof videos written as HTML and rendered to MP4 with
[HyperFrames](https://github.com/heygen-com/hyperframes) (HeyGen, Apache-2.0, no per-render fees).
Every scene is built from real assets: site copy, client map-pack screenshots, a capture of the live page.
No mockups.

Needs Node 22+ and FFmpeg. GSAP is vendored in each project's `assets/vendor/`, so renders never touch a CDN.

## panicci-promo — 22s, 1080×1920 (Reels / Shorts / TikTok)

Hook (Sammy, "A to C") → A/B/C → Desert Dog page 3 → #1 → GJJW unranked → #1 → homepage scroll → end card.

```bash
cd video/hyperframes/panicci-promo
npx hyperframes@0.8.185 check        # lint + layout + contrast
npx hyperframes@0.8.185 preview      # live Studio preview in the browser
npx hyperframes@0.8.185 render --quality delivery --output renders/panicci-promo-vertical.mp4
```

The end-card button text and URL are composition variables (`cta`, `url`), so the same film can point at
`/grade`, `/apply` or a client page without touching the scenes.

No music is baked in on purpose: add a trending sound in-app when posting.

## Reusing it for a client site launch

1. `npx hyperframes@0.8.185 init <client>-promo --resolution portrait --example blank --non-interactive`
2. Copy `assets/vendor/gsap.min.js` and `assets/fonts/` from this project, then add the client's logo, photos
   and real ranking screenshots (dated, with the search location named).
3. Swap the copy and screenshots in the scene files under `compositions/`; keep the timing.
4. `check`, then `render`.

## rogue-island-promo — 21s, 1080×1920 (case-study clip)

Rogue Island Local Kitchen & Bar, Providence: Page 4 → Page 1 → rebuilt site → 1,004,888 Google impressions
and 34,701 clicks in 12 months → 3,076 searches ranking top 3 → "Your restaurant is next."

Every number comes from Google Search Console (US, Oct 20, 2025 – Oct 19, 2026), pulled through Search Atlas on
2026-10-22. The monthly bars are the real calendar-month impressions, Oct 2025 – Sep 2026. The site shot is a
Search Atlas capture of rogueislandgroup.com from the same day. Refresh the numbers before re-posting it in a few months.

## gjjw-promo — 23.4s, 1080×1920 (case-study clip)

Gracie Jiu-Jitsu Warwick: "#1 on the map" → all 39 grid pins at #1 for "kids jiu-jitsu Warwick" → the unedited
map-pack screenshot → top-3 spots vs the next four schools (39 / 20 / 15 / 5 / 5) → #1 in 26 of 28 weekly scans
since April → "Your school is next."

Grid, competitor and weekly numbers are Search Atlas local heatmaps (business 126116, grid `2pb8.c5y6`, 5-mile
radius, 39 pins), pulled 2026-10-22; the Oct 19 scan returned no position and is left out. Competing schools are
deliberately unnamed. The pin layout follows Search Atlas's circle grid (1 + 6 + 12 + 20); every pin read #1 on
Oct 21. The screenshot is the unedited Oct 12, 2026 capture from panicciventures.com.
