// extension/coursera-content.js
//
// Goal: extract real, *user-specific* keywords/topics from whatever
// Coursera page the user is on. We collect evidence from three
// independent sources and union them — any one of them succeeding is
// enough.
//
//   1. ``__NEXT_DATA__`` hydration JSON. Coursera is a Next.js app, so
//      everything the server rendered (enrolled programs, names,
//      slugs, recently viewed courses) is sitting in a single
//      ``<script id="__NEXT_DATA__" type="application/json">`` blob.
//      We walk it recursively and pull anything that looks like a
//      course or specialization.
//
//   2. Anchor scraping with ``MutationObserver``. As cards render,
//      we collect links to /learn/, /specializations/,
//      /professional-certificates/, /programs/, plus their nearby
//      heading and surrounding context.
//
//   3. Slug mining. Even with no titles available, the URL slug
//      itself is a clean keyword ("/learn/machine-learning" →
//      "machine learning"). We surface these as fallback course
//      entries so the backend keyword extractor always has *something*
//      to chew on.
//
// All three feed into a single deduped course list keyed by URL/slug.

const COURSE_PATH_PREFIXES = [
  "/learn/",
  "/specializations/",
  "/professional-certificates/",
  "/programs/",
];

const LOGIN_HINTS = ["/login", "/auth", "/signin"];

const MAX_WAIT_MS = 15000;
const POLL_INTERVAL_MS = 500;
const MIN_COURSES_TO_CONSIDER_READY = 1;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isCourseHref(href) {
  if (!href) return false;
  try {
    const url = new URL(href, window.location.origin);
    if (!url.hostname.endsWith("coursera.org")) return false;
    return COURSE_PATH_PREFIXES.some((p) => url.pathname.startsWith(p));
  } catch {
    return false;
  }
}

function normalizeHref(href) {
  try {
    return new URL(href, window.location.origin).toString();
  } catch {
    return href;
  }
}

function slugToTitle(slug) {
  return (slug || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function looksLikeLoginPage() {
  const path = window.location.pathname.toLowerCase();
  if (LOGIN_HINTS.some((h) => path.includes(h))) return true;
  const passwordField = document.querySelector('input[type="password"]');
  return Boolean(passwordField);
}

// ---------------------------------------------------------------------------
// Source 1: __NEXT_DATA__ hydration JSON
// ---------------------------------------------------------------------------

function readNextData() {
  const tag = document.getElementById("__NEXT_DATA__");
  if (!tag || !tag.textContent) return null;
  try {
    return JSON.parse(tag.textContent);
  } catch (err) {
    console.warn("[Coursera Extractor] Failed to parse __NEXT_DATA__:", err);
    return null;
  }
}

// Walk arbitrary JSON looking for course-shaped objects. We're
// intentionally permissive — Coursera's internal payload shape changes
// often; we just need a name + something resembling a slug/id.
function harvestFromNextData(json, out) {
  const seen = new WeakSet();
  const COURSE_TYPE_HINTS = [
    "course",
    "specialization",
    "professionalcertificate",
    "program",
    "career",
  ];

  function walk(node) {
    if (!node) return;
    if (typeof node !== "object") return;
    if (seen.has(node)) return;
    seen.add(node);

    if (Array.isArray(node)) {
      for (const child of node) walk(child);
      return;
    }

    const name = node.name || node.title || node.courseName || node.displayName;
    const slug = node.slug || node.courseSlug;
    const productType = (node.productType || node.type || node.__typename || "").toString().toLowerCase();
    const looksLikeCourse =
      typeof name === "string" &&
      name.length > 2 &&
      name.length < 200 &&
      (slug || COURSE_TYPE_HINTS.some((h) => productType.includes(h)));

    if (looksLikeCourse) {
      const url = slug
        ? `https://www.coursera.org/learn/${slug}`
        : "";
      const key = url || `name:${name}`;
      if (!out.has(key)) {
        out.set(key, {
          title: name.trim(),
          url,
          context: (node.description || node.tagline || "").toString().slice(0, 240),
          source: "next-data",
        });
      }
    }

    for (const value of Object.values(node)) {
      if (value && typeof value === "object") walk(value);
    }
  }

  walk(json);
}

// ---------------------------------------------------------------------------
// Source 2: DOM anchors
// ---------------------------------------------------------------------------

function harvestFromAnchors(out) {
  const anchors = document.querySelectorAll("a[href]");
  anchors.forEach((el) => {
    const rawHref = el.getAttribute("href");
    if (!isCourseHref(rawHref)) return;

    const url = normalizeHref(rawHref);

    const heading =
      el.querySelector("h1, h2, h3, h4") ||
      el.closest("[data-test]")?.querySelector("h1, h2, h3, h4");
    const titleFromHeading = heading?.textContent?.trim();
    const titleFromText = el.textContent?.trim();
    const title =
      titleFromHeading && titleFromHeading.length > 2
        ? titleFromHeading
        : titleFromText || "";

    if (!title || title.length < 2) return;

    const card = el.closest("article, li, div[data-test], div[class*='Card']");
    let context = "";
    if (card && card !== el) {
      context = (card.textContent || "")
        .replace(title, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 240);
    }

    const existing = out.get(url);
    if (!existing || (context.length > (existing.context?.length || 0))) {
      out.set(url, { title, url, context, source: "dom" });
    }
  });
}

// ---------------------------------------------------------------------------
// Source 3: slug mining
// ---------------------------------------------------------------------------

// Even when titles are unavailable, the URL slugs themselves carry the
// topic ("learn/machine-learning" → "machine learning"). Useful when
// __NEXT_DATA__ doesn't include a name field for the user's enrolled
// items.
function harvestFromSlugs(out) {
  const anchors = document.querySelectorAll("a[href]");
  anchors.forEach((el) => {
    const rawHref = el.getAttribute("href");
    if (!isCourseHref(rawHref)) return;
    const url = normalizeHref(rawHref);
    if (out.has(url)) return;

    try {
      const parsed = new URL(url);
      const parts = parsed.pathname.split("/").filter(Boolean);
      // .../learn/<slug> or .../specializations/<slug>
      const slug = parts.length >= 2 ? parts[1] : "";
      const title = slugToTitle(slug);
      if (title && title.length >= 3) {
        out.set(url, { title, url, context: "", source: "slug" });
      }
    } catch {
      /* ignore */
    }
  });
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

function collectCourses() {
  const out = new Map();

  // Order matters: __NEXT_DATA__ has the cleanest titles, DOM next,
  // slug-derived last. Earlier sources are not overwritten by later
  // ones because we check `out.has(key)` first.
  const next = readNextData();
  if (next) harvestFromNextData(next, out);
  harvestFromAnchors(out);
  harvestFromSlugs(out);

  return Array.from(out.values());
}

function waitForCourses(onReady, onTimeout) {
  const deadline = Date.now() + MAX_WAIT_MS;
  let resolved = false;

  const finish = (courses, reason) => {
    if (resolved) return;
    resolved = true;
    observer.disconnect();
    clearInterval(pollId);
    if (courses.length > 0) onReady(courses, reason);
    else onTimeout(reason);
  };

  const check = (reason) => {
    if (resolved) return;
    const courses = collectCourses();
    if (courses.length >= MIN_COURSES_TO_CONSIDER_READY) {
      finish(courses, reason);
    } else if (Date.now() >= deadline) {
      finish(courses, `${reason}-timeout`);
    }
  };

  const observer = new MutationObserver(() => check("mutation"));
  observer.observe(document.body, { childList: true, subtree: true });

  const pollId = setInterval(() => check("poll"), POLL_INTERVAL_MS);

  check("initial");
}

function sendPayload(payload) {
  if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
    try {
      chrome.runtime.sendMessage({
        type: "COURSERA_EXTRACTED",
        payload,
      });
    } catch (err) {
      console.warn("[Coursera Extractor] sendMessage failed:", err);
    }
  } else {
    console.warn("[Coursera Extractor] chrome.runtime.sendMessage not available");
  }

  if (window.opener) {
    try {
      window.opener.postMessage(
        { source: "coursera_extractor", payload },
        "*"
      );
    } catch (err) {
      console.warn("[Coursera Extractor] window.opener postMessage failed:", err);
    }
  }
}

function run() {
  console.log("[Coursera Extractor] Running", { url: window.location.href });

  if (looksLikeLoginPage()) {
    console.warn(
      "[Coursera Extractor] Detected a login/auth page. Asking the app to surface a sign-in hint."
    );
    sendPayload({
      courses: [],
      count: 0,
      needsLogin: true,
      page: window.location.href,
      extractedAt: new Date().toISOString(),
    });
    return;
  }

  waitForCourses(
    (courses, reason) => {
      const sources = courses.reduce((acc, c) => {
        acc[c.source] = (acc[c.source] || 0) + 1;
        return acc;
      }, {});
      const payload = {
        courses,
        count: courses.length,
        page: window.location.href,
        extractedAt: new Date().toISOString(),
        readyReason: reason,
        sources,
      };
      console.log("[Coursera Extractor] Found courses:", courses.length, {
        reason,
        sources,
      });
      console.log("[Coursera Extractor] Sample:", courses.slice(0, 3));
      sendPayload(payload);
    },
    (reason) => {
      console.warn(
        "[Coursera Extractor] No courses found before timeout",
        { reason, url: window.location.href }
      );
      sendPayload({
        courses: [],
        count: 0,
        page: window.location.href,
        extractedAt: new Date().toISOString(),
        readyReason: reason,
        empty: true,
      });
    }
  );
}

if (document.readyState === "complete" || document.readyState === "interactive") {
  setTimeout(run, 250);
} else {
  window.addEventListener("DOMContentLoaded", () => setTimeout(run, 250), { once: true });
}
