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
