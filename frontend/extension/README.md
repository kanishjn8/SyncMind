# SyncMind Coursera Extractor (Chrome Extension)

A small **Manifest V3** Chrome extension that helps SyncMind read a user's
Coursera "My Learning" page from inside their own browser session — Coursera
doesn't expose a public API, so we go through the user's logged-in tab.

The extension is **optional**. If it's not installed, the backend falls back
to deriving Coursera recommendations from the user's GitHub + YouTube
signals (see [the root README](../../README.md#how-the-recommender-works)).

## Files

| File | Purpose |
| --- | --- |
| `manifest.json` | MV3 manifest — declares permissions, content scripts |
| `background.js` | Service worker; routes messages between tabs |
| `coursera-content.js` | Runs on `coursera.org`; scrapes `__NEXT_DATA__`, DOM, URL slugs |
| `landing-bridge.js` | Runs on `localhost:3000`; announces presence to the React app and forwards EXTRACTED payloads |

## How it works

1. The React app on `localhost:3000` (or `127.0.0.1:3000`) sends a `PING`
   via `postMessage`.
2. `landing-bridge.js` replies with `EXTENSION_PRESENT`.
3. When the user clicks **Connect Coursera**, the app opens
   `coursera.org/my-learning` in a new tab.
4. `coursera-content.js` waits for the page to hydrate, then collects
   evidence from three sources:
   - Recursive walk of `__NEXT_DATA__` JSON for structured course objects.
   - DOM scraping under a `MutationObserver` (Coursera lazy-renders).
   - URL slug mining (`/learn/machine-learning` → `"machine learning"`).
5. The aggregated payload is sent back through `background.js` →
   `landing-bridge.js` → the React app as an `EXTRACTED` message.
6. The app POSTs it to the backend at `/recommend-coursera`.

## Install (development)

1. Open `chrome://extensions`.
2. Toggle **Developer mode** on (top right).
3. Click **Load unpacked**.
4. Select this folder: `frontend/extension/`.
5. Pin the extension if you want a visible badge.

After editing any file here, click the reload icon on the extension card
(or bump `version` in `manifest.json`) and refresh the Coursera and
SyncMind tabs.

## Permissions

- `tabs`, `scripting` — needed by the background worker to message tabs.
- Host permissions on `coursera.org` and the local React dev origins —
  required in MV3 for `chrome.tabs.sendMessage` / `chrome.tabs.query` to
  reach those origins. Without these, the bridge silently fails.

## Notes

- The Coursera content script tries to detect login pages and tells the
  user to sign in if it lands on one.
- The frontend gives the extension a 60-second window after opening the
  Coursera tab before falling back automatically.
- This extension is **not** published to the Chrome Web Store — it is
  intended for the SyncMind developer / demo flow.
