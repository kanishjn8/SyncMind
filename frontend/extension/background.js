chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "COURSERA_EXTRACTED") {
    return;
  }

  console.log("[Coursera Bridge Background] Received extractor payload", {
    fromTabId: sender?.tab?.id,
    courseCount: message.payload?.count || 0,
  });

  chrome.tabs.query(
    { url: ["http://localhost:3000/*", "http://127.0.0.1:3000/*"] },
    (tabs) => {
      tabs.forEach((tab) => {
        if (!tab.id) return;

        chrome.tabs.sendMessage(tab.id, {
          type: "COURSERA_EXTRACTED_FOR_APP",
          payload: message.payload,
        });
      });
    }
  );

  sendResponse({ ok: true });
});
