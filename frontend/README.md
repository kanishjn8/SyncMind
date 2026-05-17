# SyncMind Frontend

React 18 single-page app built with **Create React App** (not Next.js — there's
a leftover `next.config.ts` in this folder, but `package.json` uses
`react-scripts`).

For the full project overview, architecture, and backend setup, see the
[root README](../README.md).

## Stack

- React 18 + React Router DOM 6
- Tailwind CSS
- Framer Motion (animations)
- Lucide React (icons)
- Recharts (charts)

## Layout

```
src/
├── App.jsx                ← Router, global AppContext, desktop-only guard
├── index.jsx              ← React entry
├── index.css              ← Tailwind base styles
├── pages/
│   ├── Landing.jsx        ← OAuth + platform connect flows (incl. extension bridge)
│   ├── Dashboard.jsx      ← Connected platforms, recs, jobs section
│   └── About.jsx
└── components/
    ├── Navbar.jsx
    ├── Header.jsx
    ├── PlatformCard.jsx
    ├── ConnectedPlatformCard.jsx
    ├── RecommendationCard.jsx   ← cards for repos, videos, courses, jobs
    ├── ProgressRing.jsx
    ├── FeatureCard.jsx
    ├── GlowButton.jsx
    ├── StarField.jsx
    └── ParticleBackground.jsx
```

A separate, **optional** Chrome extension lives at
[`extension/`](./extension/README.md) — it powers the Coursera connect flow
when installed but the app works without it.

## Develop

```bash
npm install
npm start
```

The app runs at `http://localhost:3000` and expects the FastAPI backend at
`http://127.0.0.1:8000` (matches the OAuth callback URLs).

## Build

```bash
npm run build
```

Outputs a static bundle to `build/` that can be served by any static host or
proxied behind the FastAPI app.

## Notes

- The app shows a desktop-only prompt below 1024px width (see `App.jsx`).
- `Dashboard.jsx` triggers the **jobs** flow on mount:
  1. fetches `https://ipapi.co/json/` for IP-based location,
  2. `POST`s it to the backend `/profile/location`, then
  3. `GET`s `/get_jobs` to render the "Jobs For You" section.
- The Coursera connect button on `Landing.jsx` first pings for the extension
  (`EXTENSION_PRESENT`). If silent, it just calls `/recommend-coursera` with
  an empty history and lets the backend fall back to cross-platform inference.
