// extension/landing-bridge.js
//
// Bridges messages from the extension's service worker into the
// `window.message` event stream the React app listens on. Also
// announces the extension's presence to the page so the app can
// gracefully fall back when no extension is installed.

const announcePresence = () => {
  try {
    window.postMessage(
      {
        source: "coursera_extractor",
        type: "EXTENSION_PRESENT",
        version: chrome.runtime?.getManifest?.()?.version || null,
      },
      "*"
    );
  } catch (err) {
    console.warn("[Coursera Bridge Landing] failed to announce presence:", err);
  }
};

// Initial announce on load — content scripts run at document_idle, so
// this may fire before or after the app's `useEffect` listeners attach.
// We also re-announce on PING so the app can ask at any later time.
announcePresence();

window.addEventListener("message", (event) => {
  if (event.data?.source === "coursera_extractor_app" && event.data?.type === "PING") {
    announcePresence();
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "COURSERA_EXTRACTED_FOR_APP") {
    return;
  }

  console.log("[Coursera Bridge Landing] Forwarding payload to app page", {
    courseCount: message.payload?.count || 0,
  });

  window.postMessage(
    {
      source: "coursera_extractor",
      type: "EXTRACTED",
      payload: message.payload,
      via: "extension_background_bridge",
    },
    "*"
  );
});
