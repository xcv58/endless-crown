# Endless Crown website

The public marketing website for Endless Crown, intended for `https://crown.jenny.media/`.

## Local preview

From this directory run `python3 -m http.server 4173 --bind 127.0.0.1 --directory dist`, then open `http://127.0.0.1:4173/`.

This is a static website with no dependencies, build step, analytics, or forms. `dist/` contains the authored public files and must be tracked, not treated as generated output. Serve `dist/` as the document root. Small scripts provide appearance preferences and the video play overlay; pages and native video controls still work without JavaScript.

## Content and assets

- Public name: **Endless Crown**. CrownSpin remains the internal app project name.
- App Store: https://apps.apple.com/us/app/endless-crown/id6777250620
- Screenshot and icon files come from the app's existing App Store assets.
- `demo.mp4` is a 720 × 1280, 30 fps web copy of the original 27-second Reddit launch video. It retains the original sequence, captions, and audio. Playback starts only when requested, with sound enabled by default and native mute controls available. The 20 MB original remains outside the repository at `/Users/yihong/Movies/2026-06-20 Endless Crown/exports/endless-crown-reddit-draft-v18-longer-haptic-samples.mp4`.
- The demo uses `preload="none"`, a poster frame, native playback controls, an explicit play button, and a text description. No Reddit player or third-party script is embedded.
- Appearance follows the system by default. The sun/moon button switches directly between Light and Dark and stores only an explicit manual preference in `endless-crown-appearance`; the footer’s “Use system appearance” button clears it. All pages share this setting, respond to system and cross-tab changes, and remain usable when storage is blocked.
- The App Store badge is Apple’s unmodified preferred black SVG from https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg. It is displayed at 60 px high with at least 15 px of clear space, and is not recolored or animated in either theme.
- Haptic categories match `HapticPattern.swift`.
- Privacy wording mirrors the repository's `PrivacyPolicy.md`.
- The hero shows US$0.99 as a one-time purchase, verified against the U.S. App Store listing on September 10, 2026, with a note that local prices vary by country or region. Recheck this amount when app pricing changes.
- The theme toggle occupies the top-right header position on every page, including mobile; the App Store badge remains in the hero.
- Canonical URLs and the sitemap use the requested custom domain.

Design references: Jenny Media's apps directory, FrameWink, and Heart Rate Insights. The site uses real app footage, unchanged app screenshots, a charcoal dark theme, and a silver-white light theme.

## Verification

Run `node --test tests/interaction.test.mjs` for appearance persistence, system changes, blocked storage, and video playback success/failure behavior. These are script-level checks, not browser visual QA.

## Publishing

Vercel hosts the production website and manages DNS for `jenny.media`.

- Project: `endless-crown`, under `xcv58s-projects`.
- Connected repository: `xcv58/endless-crown`; production branch: `master`.
- Root directory: `website`; published output directory: `dist`.
- `vercel.json` runs the existing interaction checks before publishing. There are no dependencies to install or application files to compile.
- Pull requests receive Vercel preview deployments; merges to `master` trigger production deployments.
- Custom domain: `crown.jenny.media`, assigned to this Vercel project.

Only `dist/` is served. The native app and launch documents are outside the public output. The earlier Sites preview is separate from production; its local hosting metadata is ignored by Git.
