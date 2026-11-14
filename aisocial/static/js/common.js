// Shared helpers for every page. Plain ES module, no dependencies.
// All text goes into the page with textContent (never innerHTML).

// --- interface language: the server sets <html lang>, every visible text is written in both languages ---
export const LANG = document.documentElement.lang === "el" ? "el" : "en";
export const LOCALE = LANG === "el" ? "el-GR" : "en-GB"; // en-GB: 24-hour clock, day before month

/** The text in the interface language: L(english, greek). */
export const L = (en, gr) => (LANG === "el" ? gr : en);

/** plural(3, "{n} post", "{n} posts", "{n} post", "{n} posts"): singular only for exactly one. */
export const plural = (n, enOne, enMany, grOne, grMany) => L(n === 1 ? enOne : enMany, n === 1 ? grOne : grMany).replaceAll("{n}", String(n));

export class ApiError extends Error {}

/** Call the JSON API. Throws ApiError with a message that can be shown to the user. */
export async function api(path, { method = "GET", body, form } = {}) {
  const headers = { "X-AISocial-Request": "1", Accept: "application/json" };
  const init = { method, headers, credentials: "same-origin" };
  if (form) {
    init.body = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(path, init);
  } catch {
    throw new ApiError(L("Can't reach AI Social. Is the app still running?", "Δεν υπάρχει σύνδεση με το AI Social. Τρέχει ακόμα το πρόγραμμα;"));
  }
  let data = null;
  try {
    data = await resp.json();
  } catch {
    /* not JSON */
  }
  if (!resp.ok || !data || data.ok === false) {
    throw new ApiError((data && data.error) || L(`Error ${resp.status}. Try again.`, `Σφάλμα ${resp.status}. Δοκίμασε ξανά.`));
  }
  return data;
}

const PROPS = new Set(["value", "checked", "disabled", "hidden", "selected", "readOnly", "required", "multiple"]);

/** el("button", {class: "btn", text: "OK", on: {click() {}}}, ...children) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "on") for (const [event, fn] of Object.entries(value)) node.addEventListener(event, fn);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (PROPS.has(key)) node[key] = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

/** node.replaceChildren() that skips null/undefined/false like el() does (the DOM would show "null"). */
export function fill(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

// --- SVG and icons (el() cannot build SVG: it needs the SVG namespace) ---
const SVG_NS = "http://www.w3.org/2000/svg";

export function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key === "on") for (const [event, fn] of Object.entries(value)) node.addEventListener(event, fn);
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child);
  }
  return node;
}

// 24×24 line drawings. The shell's copies live in templates/_icons.html.
const ICONS = {
  home: ["M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"],
  pen: ["M4.5 19.5h4l10-10a2.1 2.1 0 0 0-3-3l-10 10z", "M14 8l3 3"],
  calendar: [["rect", { x: 3.5, y: 5, width: 17, height: 15, rx: 2.5 }], "M3.5 10h17M8 3v4M16 3v4"],
  sliders: ["M4 7h9M17 7h3M4 17h3M11 17h9", ["circle", { cx: 15, cy: 7, r: 2 }], ["circle", { cx: 9, cy: 17, r: 2 }]],
  sparkle: ["M11 3.5l1.9 5.1 5.1 1.9-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9z", "M18.5 14.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8z"],
  clock: [["circle", { cx: 12, cy: 12, r: 8.5 }], "M12 7.5V12l3 2"],
  image: [["rect", { x: 3.5, y: 4.5, width: 17, height: 15, rx: 2.5 }], ["circle", { cx: 9, cy: 10, r: 1.8 }], "M20.5 16l-5-5-9.5 8.5"],
  refresh: ["M19.5 12a7.5 7.5 0 1 1-2.2-5.3", "M19.5 4.5v4h-4"],
  dice: [
    ["rect", { x: 4, y: 4, width: 16, height: 16, rx: 3.5 }],
    ["circle", { cx: 9, cy: 9, r: 1.3, class: "fill" }],
    ["circle", { cx: 12, cy: 12, r: 1.3, class: "fill" }],
    ["circle", { cx: 15, cy: 15, r: 1.3, class: "fill" }],
  ],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  alert: ["M10.3 4.9a2 2 0 0 1 3.4 0l7.2 12.6a2 2 0 0 1-1.7 3H4.8a2 2 0 0 1-1.7-3z", "M12 9.5V14", ["circle", { cx: 12, cy: 17, r: 0.9, class: "fill" }]],
  close: ["M6.5 6.5l11 11M17.5 6.5l-11 11"],
  plus: ["M12 5v14M5 12h14"],
  minus: ["M6.5 12h11"],
  send: ["M4.5 11.5 19.5 4.5l-5 15-3-6.5z", "M11.5 13 19.5 4.5"],
  external: ["M14 4.5h5.5V10", "M19.5 4.5 11 13", "M18 14v4.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H10"],
  table: [["rect", { x: 4, y: 5, width: 16, height: 14, rx: 2 }], "M4 10h16M4 14.5h16M10 10v9"],
  chart: ["M5 20v-8M10 20V6M15 20v-7M20 20V9"],
  upload: ["M12 16V5", "M7.5 9.5 12 5l4.5 4.5", "M5 19.5h14"],
  contrast: [["circle", { cx: 12, cy: 12, r: 8 }], ["path", { d: "M12 4a8 8 0 0 1 0 16z", class: "fill" }]],
};

export function icon(name, cls = "") {
  const parts = ICONS[name] || [];
  return svg(
    "svg",
    { class: cls ? `icon ${cls}` : "icon", viewBox: "0 0 24 24", "aria-hidden": "true", focusable: "false" },
    parts.map((part) => (typeof part === "string" ? svg("path", { d: part }) : svg(part[0], part[1]))),
  );
}

/** Children for a button or link with an icon: el("button", {...}, ...withIcon("send", label)) */
export const withIcon = (name, text) => [icon(name), el("span", { text })];

export function toast(message, kind = "info", timeout = 5000) {
  const box = document.getElementById("toasts");
  if (!box) return;
  const symbol = { ok: "check", error: "alert", warn: "alert" }[kind];
  const node = el(
    "div",
    { class: `toast toast-${kind}`, role: kind === "error" ? "alert" : "status" },
    symbol ? icon(symbol) : null,
    el("span", { class: "toast-text", text: message }),
    el("button", { class: "toast-close", type: "button", "aria-label": L("Close", "Κλείσιμο") }, icon("close")),
  );
  node.querySelector(".toast-close").addEventListener("click", () => node.remove());
  box.append(node);
  setTimeout(() => node.remove(), timeout);
}

/** Disable a button and show a spinner while task() runs. Icons inside the button survive. */
export async function busy(button, task, busyLabel) {
  if (!button) return task();
  if (button.getAttribute("aria-busy") === "true") return undefined;
  const content = [...button.childNodes];
  button.setAttribute("aria-busy", "true");
  button.disabled = true;
  if (busyLabel) button.replaceChildren(el("span", { text: busyLabel }));
  try {
    return await task();
  } finally {
    button.removeAttribute("aria-busy");
    button.disabled = false;
    if (busyLabel) button.replaceChildren(...content);
  }
}

/** Like busy(), but errors become a toast instead of being thrown. */
export async function action(button, task, busyLabel) {
  try {
    return await busy(button, task, busyLabel);
  } catch (err) {
    toast(err && err.message ? err.message : String(err), "error", 10000);
    return undefined;
  }
}

/** Two-click confirmation without browser dialogs: the first click arms the button. */
export function armed(button, task, prompt = L("Sure? Click again", "Σίγουρα; Πάτα ξανά")) {
  const content = [...button.childNodes];
  let timer = null;
  const reset = () => {
    clearTimeout(timer);
    timer = null;
    button.classList.remove("armed");
    button.replaceChildren(...content);
  };
  button.addEventListener("click", () => {
    if (!timer) {
      button.classList.add("armed");
      button.replaceChildren(el("span", { text: prompt }));
      timer = setTimeout(reset, 4000);
      return;
    }
    reset();
    task();
  });
  return button;
}

let uid = 0;
export function field(label, input, hint) {
  if (!input.id) input.id = `f${++uid}`;
  return el(
    "div",
    { class: "field" },
    el("label", { for: input.id, text: label }),
    input,
    hint ? el("p", { class: "hint" }, typeof hint === "string" ? linkify(hint) : hint) : null,
  );
}

const URL_IN_TEXT = /https?:\/\/[^\s<>"«»]+/g;

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Addresses of this app (e.g. a redirect URL to paste elsewhere) are values to copy, not links to open. */
function isOwnUrl(url) {
  try {
    const { hostname, origin } = new URL(url);
    return LOCAL_HOSTS.has(hostname) || hostname.endsWith(".localhost") || origin === location.origin;
  } catch {
    return false;
  }
}

/** Text with clickable http(s) links, as a DocumentFragment. The app's own addresses stay plain code. */
export function linkify(text) {
  const source = String(text);
  const frag = document.createDocumentFragment();
  let pos = 0;
  for (const match of source.matchAll(URL_IN_TEXT)) {
    let url = match[0];
    while (/[.,;:!?)\]]$/.test(url)) url = url.slice(0, -1);
    frag.append(source.slice(pos, match.index));
    frag.append(isOwnUrl(url)
      ? el("code", { text: url })
      : el("a", { href: url, target: "_blank", rel: "noopener noreferrer", text: url }));
    pos = match.index + url.length;
  }
  frag.append(source.slice(pos));
  return frag;
}

// --- dates (always the browser's local time; days are stepped with setDate, never by adding 24h) ---
const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  // 24-hour clock in both languages: "09:00", not "9:00 am" (whose final dot clashes with sentence punctuation).
  weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
export const fmtDateTime = (ts) => (ts ? dateFormat.format(new Date(ts * 1000)) : "");

const timeFormat = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
export const fmtTime = (ts) => timeFormat.format(new Date(ts * 1000));

const longDayFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" });
const longDayYearFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

export function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

export function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** Whole calendar days from today to `date` (0 = today, 1 = tomorrow, -1 = yesterday). */
export function daysFromToday(date) {
  return Math.round((startOfDay(date) - startOfDay(new Date())) / 86400000);
}

/** "Today", "Tomorrow", "Yesterday", or e.g. "Monday 16 November". */
export function dayTitle(date) {
  const diff = daysFromToday(date);
  if (diff === 0) return L("Today", "Σήμερα");
  if (diff === 1) return L("Tomorrow", "Αύριο");
  if (diff === -1) return L("Yesterday", "Χθες");
  const sameYear = new Date(date).getFullYear() === new Date().getFullYear();
  return (sameYear ? longDayFormat : longDayYearFormat).format(date);
}

const relative = new Intl.RelativeTimeFormat(LANG, { numeric: "auto" });
export function fromNow(ts) {
  const diff = ts - Date.now() / 1000;
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, seconds] of units) {
    if (Math.abs(diff) >= seconds) return relative.format(Math.round(diff / seconds), unit);
  }
  return diff >= 0 ? L("in a few seconds", "σε λίγα δευτερόλεπτα") : L("just now", "μόλις τώρα");
}

/** Value for <input type="datetime-local"> in the browser's time zone. */
export function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Same rules as the server (aisocial/platforms/x.py): URLs count 23,
// Latin/Greek/Cyrillic 1, emoji and most other characters 2.
const URL_RE = /https?:\/\/\S+/giu;
function weigh(text) {
  let total = 0;
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    const light = cp <= 0x10ff || (cp >= 0x2000 && cp <= 0x200d) || (cp >= 0x2010 && cp <= 0x201f) || (cp >= 0x2032 && cp <= 0x2037);
    total += light ? 1 : 2;
  }
  return total;
}

export function countChars(platform, text) {
  const value = (text || "").trim();
  if (platform !== "x") return [...value].length;
  const normalized = value.normalize("NFC");
  let total = 0;
  let pos = 0;
  for (const match of normalized.matchAll(URL_RE)) {
    total += weigh(normalized.slice(pos, match.index)) + 23;
    pos = match.index + match[0].length;
  }
  return total + weigh(normalized.slice(pos));
}

const BADGES = { x: "𝕏", linkedin: "in", facebook: "f" };
export function platformBadge(key, size = "") {
  return el("span", { class: `badge badge-${key}${size ? ` badge-${size}` : ""}`, "aria-hidden": "true", text: BADGES[key] || "•" });
}

export function copyBox(value, label) {
  const input = el("input", { type: "text", readOnly: true, value, class: "mono", "aria-label": label || L("Value", "Τιμή") });
  const button = el("button", {
    type: "button",
    class: "btn btn-sm",
    text: L("Copy", "Αντιγραφή"),
    on: {
      click: async () => {
        try {
          await navigator.clipboard.writeText(value);
          toast(L("Copied.", "Αντιγράφηκε."), "ok", 2000);
        } catch {
          input.select();
          toast(L("Press Ctrl+C (or Cmd+C) to copy.", "Πάτα Ctrl+C (ή Cmd+C) για αντιγραφή."));
        }
      },
    },
  });
  return el("div", { class: "copy-box" }, label ? el("span", { class: "small muted", text: label }) : null, el("div", { class: "input-row" }, input, button));
}

/** Collapsible step-by-step guide ({title, summary, steps, notes, copy}). */
export function guideBox(guide, { open = false, label = L("Step-by-step guide", "Οδηγός βήμα-βήμα") } = {}) {
  if (!guide) return null;
  return el(
    "details",
    { class: "guide", open },
    el("summary", { text: label }),
    el(
      "div",
      { class: "guide-body" },
      el("ol", { class: "steps" }, guide.steps.map((step) => el("li", {}, linkify(step)))),
      guide.copy ? copyBox(guide.copy, L("Copy exactly this:", "Αντέγραψε αυτό ακριβώς:")) : null,
      guide.notes && guide.notes.length ? el("ul", { class: "notes" }, guide.notes.map((note) => el("li", {}, linkify(note)))) : null,
    ),
  );
}

export function errorBox(message) {
  return el("div", { class: "notice notice-danger" }, icon("alert"), el("div", {}, el("strong", { text: L("Something went wrong.", "Κάτι πήγε στραβά.") }), " ", el("span", { text: message })));
}

/** Read and remove query parameters (e.g. ?linkedin=connected after OAuth). */
export function takeParams(...names) {
  const url = new URL(location.href);
  const out = {};
  for (const name of names) {
    if (url.searchParams.has(name)) {
      out[name] = url.searchParams.get(name);
      url.searchParams.delete(name);
    }
  }
  if (Object.keys(out).length) history.replaceState(null, "", url.pathname + url.search + url.hash);
  return out;
}

/**
 * English or Greek. The choice is saved for the whole app, then the page reloads in it.
 * `anchor` (e.g. "language") brings the reloaded page back to the same section.
 */
export function languagePicker({ anchor } = {}) {
  const name = `ui-language-${++uid}`;
  const choices = [["en", "English"], ["el", "Ελληνικά"]]; // i18n-data: each language is named in itself
  const inputs = [];
  async function choose(language) {
    inputs.forEach((input) => { input.disabled = true; });
    try {
      await api("/api/ui", { method: "PUT", body: { language } });
      if (anchor) history.replaceState(null, "", `${location.pathname}${location.search}#${anchor}`);
      location.reload();
    } catch (err) {
      inputs.forEach((input) => { input.disabled = false; input.checked = input.value === LANG; });
      toast(err.message, "error");
    }
  }
  const seg = el("div", { class: "seg", role: "radiogroup", "aria-label": L("Interface language", "Γλώσσα εφαρμογής") }, choices.map(([value, label]) => {
    const input = el("input", { type: "radio", name, value, checked: value === LANG, on: { change: () => choose(value) } });
    inputs.push(input);
    return el("label", { lang: value }, input, el("span", { text: label }));
  }));
  return el("div", { class: "lang-pick" }, seg);
}

export const storage = {
  get(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || "null");
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage blocked: drafts are just not remembered */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};
