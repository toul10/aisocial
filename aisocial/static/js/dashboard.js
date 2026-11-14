// Home: what goes out this week, how much went out lately, and what needs attention.
// Days and weeks are bucketed here, in the browser's local time (weeks start on Monday).
import {
  addDays, api, daysFromToday, dayTitle, el, errorBox, fill, fmtTime, fromNow, icon, L, LOCALE, platformBadge, plural,
  startOfDay, svg, toLocalInput, withIcon,
} from "./common.js";

const app = document.getElementById("app");
const WEEKS = 12;
const DAY_POSTS_SHOWN = 4;
const SVG_MAX_BAR = 24;

const fullDate = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const weekdayShort = new Intl.DateTimeFormat(LOCALE, { weekday: "short" });
const dayMonth = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long" });
const dayMonthShort = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" });

let state = null; // /api/state: accounts, ai, platforms
let data = null; // /api/dashboard
let chartObserver = null;

const nowSec = () => Date.now() / 1000;
const labelOf = (key) => (state.platforms.find((p) => p.key === key) || { label: key }).label;

/** "16–22 November" or "28 November – 4 December"; Greek says "16 to 22 November" in words. */
function spanText(first, last, format) {
  if (first.getMonth() === last.getMonth()) {
    return L(`${first.getDate()}–${format.format(last)}`, `${first.getDate()} έως ${format.format(last)}`);
  }
  return L(`${format.format(first)} – ${format.format(last)}`, `${format.format(first)} έως ${format.format(last)}`);
}

function greeting() {
  const hour = new Date().getHours();
  if (hour >= 4 && hour < 12) return L("Good morning", "Καλημέρα");
  return hour >= 12 && hour < 18 ? L("Good afternoon", "Καλησπέρα") : L("Good evening", "Καλησπέρα");
}

/** "The next post goes out tomorrow at 09:00." */
function nextSentence() {
  if (!data.next_at) {
    return (data.counts.scheduled || 0)
      ? L("Your scheduled posts are more than a week away.", "Τα προγραμματισμένα posts σου είναι πιο μακριά από μία εβδομάδα.")
      : L("Nothing is scheduled. Write a post and choose when it goes out.", "Δεν έχεις προγραμματισμένα posts. Γράψε ένα και διάλεξε πότε θα βγει.");
  }
  const when = new Date(data.next_at * 1000);
  const diff = daysFromToday(when);
  if (diff === 0) return L(`The next post goes out today at ${fmtTime(data.next_at)}.`, `Το επόμενο post βγαίνει σήμερα στις ${fmtTime(data.next_at)}.`);
  if (diff === 1) return L(`The next post goes out tomorrow at ${fmtTime(data.next_at)}.`, `Το επόμενο post βγαίνει αύριο στις ${fmtTime(data.next_at)}.`);
  return L(`The next post is on ${dayTitle(when)}, ${fmtTime(data.next_at)}.`, `Το επόμενο post είναι για ${dayTitle(when)}, ${fmtTime(data.next_at)}.`);
}

function header() {
  return el(
    "header",
    { class: "dash-head" },
    el("p", { class: "dash-date", text: fullDate.format(new Date()) }),
    el("h1", { text: greeting() }),
    el("p", { class: "lead", text: nextSentence() }),
  );
}

// --- first steps (only while something basic is missing) ---
function onboarding() {
  const ready = state.accounts.filter((a) => a.ready);
  const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
  const writer = state.ai.text_provider === "openai" ? "OpenAI" : "Claude";
  const steps = [
    {
      done: Boolean(state.ai.text_provider),
      title: L("AI for writing", "AI για τα κείμενα"),
      doneText: L(`${writer} writes your posts.`, `Γράφει το ${writer}.`),
      todo: L("Add an API key so the AI can write your posts.", "Βάλε ένα API key για να γράφει το AI τα posts σου."),
      href: "/settings#ai",
      cta: L("Add AI key", "Βάλε AI key"),
    },
    {
      done: ready.length > 0,
      title: L("A social account", "Ένας λογαριασμός social"),
      doneText: ready.map((a) => a.name).join(", "),
      todo: L("Connect X, LinkedIn or a Facebook Page.", "Σύνδεσε το X, το LinkedIn ή μια σελίδα στο Facebook."),
      href: "/settings#accounts",
      cta: L("Connect an account", "Σύνδεσε λογαριασμό"),
    },
    {
      done: total > 0,
      title: L("Your first post", "Το πρώτο σου post"),
      doneText: L("Done.", "Έγινε."),
      todo: L("Make a test post to see that everything works.", "Κάνε ένα δοκιμαστικό post για να δεις ότι όλα δουλεύουν."),
      href: "/new",
      cta: L("Write your first post", "Γράψε το πρώτο post"),
    },
  ];
  if (steps.every((s) => s.done)) return null;
  const firstTodo = steps.findIndex((s) => !s.done);
  return el(
    "section",
    { class: "card onboard", "aria-labelledby": "onboard-title" },
    el("h2", { id: "onboard-title", text: L("Start here", "Ξεκίνα εδώ") }),
    el("ol", { class: "onboard-steps" }, steps.map((step, index) => el(
      "li",
      { class: step.done ? "done" : index === firstTodo ? "current" : "" },
      el("span", { class: "onboard-mark" }, step.done ? icon("check") : String(index + 1)),
      el(
        "div",
        { class: "onboard-text" },
        el("strong", { text: step.title }),
        el("span", { class: "small muted", text: step.done ? step.doneText : step.todo }),
      ),
      step.done ? null : el("a", { class: `btn btn-sm${index === firstTodo ? " btn-primary" : ""}`, href: step.href, text: step.cta }),
    ))),
  );
}

// --- the week ---
/** The time a "+" on that day suggests: 09:00, or (today, later on) a full hour at least 10 minutes away. */
function suggestedTime(day) {
  const at = new Date(day);
  at.setHours(9, 0, 0, 0);
  if (at.getTime() > Date.now() + 10 * 60 * 1000) return at;
  const next = new Date(Date.now() + 10 * 60 * 1000);
  next.setMinutes(0, 0, 0);
  next.setHours(next.getHours() + 1);
  return startOfDay(next).getTime() === startOfDay(day).getTime() ? next : null;
}

function overdueNotice(count) {
  const text = count === 1
    ? L(
      "A scheduled post should have gone out already. It will be sent within a few seconds, or marked “Failed” if it is more than 6 hours late.",
      "Ένα προγραμματισμένο post έπρεπε να έχει βγει ήδη. Θα σταλεί μέσα σε λίγα δευτερόλεπτα, ή θα σημειωθεί «Απέτυχε» αν άργησε πάνω από 6 ώρες.",
    )
    : L(
      `${count} scheduled posts should have gone out already. They will be sent within a few seconds; any that are more than 6 hours late are marked “Failed”.`,
      `${count} προγραμματισμένα posts έπρεπε να έχουν βγει ήδη. Θα σταλούν μέσα σε λίγα δευτερόλεπτα, ή θα σημειωθούν «Απέτυχε» όσα άργησαν πάνω από 6 ώρες.`,
    );
  return el("div", { class: "notice notice-warn" }, icon("alert"), el("span", { text }));
}

function weekView() {
  const today = startOfDay(new Date());
  const days = Array.from({ length: 7 }, (_, i) => addDays(today, i));
  const byDay = new Map(days.map((d) => [d.getTime(), []]));
  const overdue = [];
  for (const post of data.upcoming) {
    if (post.scheduled_at < nowSec()) {
      overdue.push(post);
      continue;
    }
    const key = startOfDay(new Date(post.scheduled_at * 1000)).getTime();
    if (byDay.has(key)) byDay.get(key).push(post);
  }
  const lastDay = days[6];
  const range = spanText(days[0], lastDay, dayMonth);

  const columns = days.map((day, index) => {
    const posts = byDay.get(day.getTime());
    const at = suggestedTime(day);
    const name = index === 0 ? L("Today", "Σήμερα") : index === 1 ? L("Tomorrow", "Αύριο") : weekdayShort.format(day);
    const shown = posts.slice(0, DAY_POSTS_SHOWN);
    return el(
      "li",
      { class: `day${index === 0 ? " today" : ""}${posts.length ? "" : " is-empty"}` },
      el("div", { class: "day-head" }, el("span", { class: "day-name", text: name }), el("span", { class: "day-num", text: String(day.getDate()) })),
      el("ul", { class: "day-posts" }, shown.map((post) => el(
        "li",
        {},
        el(
          "a",
          { class: "slot", href: "/posts?status=scheduled", title: `${post.account_name}: ${post.text}` },
          el("span", { class: "slot-top" }, el("span", { class: "slot-time", text: fmtTime(post.scheduled_at) }), platformBadge(post.platform, "xs")),
          el("span", { class: "slot-text", text: post.text }),
        ),
      ))),
      posts.length > shown.length ? el("a", { class: "day-more", href: "/posts?status=scheduled", text: L(`${posts.length - shown.length} more`, `και ${posts.length - shown.length} ακόμα`) }) : null,
      at
        ? el(
          "a",
          { class: "day-add", href: `/new?at=${encodeURIComponent(toLocalInput(at))}`, "aria-label": L(`New post for ${dayTitle(day)}`, `Νέο post για ${dayTitle(day)}`) },
          icon("plus"),
          el("span", { text: L("Add", "Προσθήκη") }),
        )
        : null,
    );
  });

  return el(
    "section",
    { class: "week-wrap", "aria-labelledby": "week-title" },
    el(
      "div",
      { class: "section-head" },
      el("h2", { id: "week-title", text: L("Your week", "Η εβδομάδα σου") }),
      el("span", { class: "muted small", text: range }),
      el("a", { class: "section-link", href: "/posts?status=scheduled", text: L("All scheduled", "Όλα τα προγραμματισμένα") }),
    ),
    overdue.length ? overdueNotice(overdue.length) : null,
    el("ol", { class: `week${[...byDay.values()].some((list) => list.length) ? "" : " no-posts"}` }, columns),
  );
}

// --- key figures ---
function kpis() {
  const now = nowSec();
  const last30 = data.published.filter((p) => p.at >= now - 30 * 86400).length;
  const prev30 = data.published.filter((p) => p.at >= now - 60 * 86400 && p.at < now - 30 * 86400).length;
  const scheduled = data.counts.scheduled || 0;
  const failed = data.counts.failed || 0;
  const ready = state.accounts.filter((a) => a.ready).length;
  const waiting = state.accounts.length - ready;
  const tile = (label, value, sub, extra = "") => el(
    "div",
    { class: `kpi${extra}` },
    el("span", { class: "kpi-label", text: label }),
    el("span", { class: "kpi-value", text: String(value) }),
    el("span", { class: "kpi-sub" }, sub),
  );
  const next = data.next_at ? L(`Next: ${dayTitle(new Date(data.next_at * 1000))}, ${fmtTime(data.next_at)}`, `Επόμενο: ${dayTitle(new Date(data.next_at * 1000))}, ${fmtTime(data.next_at)}`) : L("None this week", "Κανένα αυτή την εβδομάδα");
  return el(
    "section",
    { class: "kpis", "aria-label": L("Summary", "Σύνοψη") },
    tile(L("Scheduled", "Προγραμματισμένα"), scheduled, next),
    tile(L("Published, last 30 days", "Δημοσιεύτηκαν σε 30 μέρες"), last30, L(`The 30 days before: ${prev30}`, `Τις 30 μέρες πριν: ${prev30}`)),
    tile(
      L("Need attention", "Θέλουν προσοχή"),
      failed,
      failed
        ? el("a", { href: "/posts?status=failed" }, icon("alert"), el("span", { text: L("See failed posts", "Δες τα αποτυχημένα") }))
        : el("span", { class: "kpi-ok" }, icon("check"), el("span", { text: L("No problems", "Κανένα πρόβλημα") })),
      failed ? " kpi-alert" : "",
    ),
    tile(
      L("Accounts ready", "Έτοιμοι λογαριασμοί"),
      ready,
      waiting
        ? el("a", { href: "/settings#accounts", text: plural(waiting, "{n} needs setup", "{n} need setup", "{n} θέλει ρύθμιση", "{n} θέλουν ρύθμιση") })
        : state.accounts.length ? L("All ready", "Όλοι έτοιμοι") : el("a", { href: "/settings#accounts", text: L("Add your first", "Πρόσθεσε τον πρώτο") }),
    ),
  );
}

// --- posts per week (column chart, one series) ---
function startOfWeek(date) {
  const day = startOfDay(date);
  return addDays(day, -((day.getDay() + 6) % 7));
}

function weeklyBuckets() {
  const thisWeek = startOfWeek(new Date());
  const buckets = Array.from({ length: WEEKS }, (_, i) => {
    const start = addDays(thisWeek, -7 * (WEEKS - 1 - i));
    return { start, end: addDays(start, 7), total: 0, byPlatform: {} };
  });
  for (const post of data.published) {
    const t = post.at * 1000;
    const bucket = buckets.find((b) => t >= b.start.getTime() && t < b.end.getTime());
    if (bucket) {
      bucket.total += 1;
      bucket.byPlatform[post.platform] = (bucket.byPlatform[post.platform] || 0) + 1;
    }
  }
  return buckets;
}

const weekLabel = (bucket) => spanText(bucket.start, addDays(bucket.start, 6), dayMonthShort);

function niceScale(max) {
  const target = Math.max(max, 4);
  for (const step of [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]) {
    if (target / step <= 4) return { step, top: Math.ceil(target / step) * step };
  }
  const step = 10 ** Math.ceil(Math.log10(target / 4));
  return { step, top: Math.ceil(target / step) * step };
}

/** A column with a 4px rounded data end and a square base. */
function columnPath(x, base, width, height) {
  const r = Math.min(4, width / 2, height);
  const top = base - height;
  return `M${x},${base}V${top + r}A${r},${r} 0 0 1 ${x + r},${top}H${x + width - r}A${r},${r} 0 0 1 ${x + width},${top + r}V${base}Z`;
}

function drawWeekly(box, buckets, tip) {
  const width = Math.max(280, Math.floor(box.clientWidth || 640));
  const pad = { top: 26, right: 4, bottom: 28, left: 30 };
  const plotH = 170;
  const height = pad.top + plotH + pad.bottom;
  const plotW = width - pad.left - pad.right;
  const band = plotW / buckets.length;
  const barW = Math.min(SVG_MAX_BAR, Math.max(6, band * 0.55));
  const { step, top } = niceScale(Math.max(...buckets.map((b) => b.total)));
  const base = pad.top + plotH;
  const y = (v) => base - (v / top) * plotH;
  const current = buckets.length - 1;
  const maxIndex = buckets.reduce((best, b, i) => (b.total > buckets[best].total ? i : best), 0);
  const labelEvery = band < 46 ? 2 : 1;

  const grid = [];
  for (let v = 0; v <= top; v += step) {
    grid.push(svg("line", { class: v === 0 ? "viz-axis" : "viz-grid", x1: pad.left, x2: width - pad.right, y1: y(v), y2: y(v) }));
    grid.push(svg("text", { class: "viz-tick", x: pad.left - 8, y: y(v), dy: "0.32em", "text-anchor": "end", text: String(v) }));
  }

  const marks = buckets.map((bucket, i) => {
    const x = pad.left + i * band + (band - barW) / 2;
    const h = bucket.total ? Math.max(2, (bucket.total / top) * plotH) : 0;
    const group = svg("g", { class: `viz-col${i === current ? " current" : ""}` });
    if (h) group.append(svg("path", { d: columnPath(x, base, barW, h) }));
    const showValue = bucket.total && (i === current || i === maxIndex);
    if (showValue) group.append(svg("text", { class: "viz-value", x: x + barW / 2, y: base - h - 7, "text-anchor": "middle", text: String(bucket.total) }));
    if (i % labelEvery === (current % labelEvery)) {
      group.append(svg("text", {
        class: "viz-xlabel", x: pad.left + i * band + band / 2, y: base + 18, "text-anchor": "middle",
        text: i === current ? L("Now", "Τώρα") : dayMonthShort.format(bucket.start),
      }));
    }
    const hit = svg("rect", {
      class: "viz-hit", x: pad.left + i * band, y: pad.top - 10, width: band, height: plotH + 10, tabindex: "0",
      role: "img", "aria-label": L(`Week ${weekLabel(bucket)}: ${plural(bucket.total, "{n} post", "{n} posts", "{n} post", "{n} posts")}`, `Εβδομάδα ${weekLabel(bucket)}: ${plural(bucket.total, "{n} post", "{n} posts", "{n} post", "{n} posts")}`),
    });
    const show = () => {
      group.classList.add("active");
      fill(
        tip,
        el("strong", { text: plural(bucket.total, "{n} post", "{n} posts", "{n} post", "{n} posts") }),
        el("span", { class: "viz-tip-label", text: L(`Week ${weekLabel(bucket)}`, `Εβδομάδα ${weekLabel(bucket)}`) }),
        Object.entries(bucket.byPlatform).map(([key, n]) => el("span", { class: "viz-tip-row" }, el("span", { text: labelOf(key) }), el("span", { text: String(n) }))),
      );
      tip.hidden = false;
      const left = Math.min(Math.max(pad.left + i * band + band / 2, 70), width - 70);
      tip.style.setProperty("left", `${left}px`);
      tip.style.setProperty("top", `${Math.max(0, base - h - 12)}px`);
    };
    const hide = () => {
      group.classList.remove("active");
      tip.hidden = true;
    };
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", show);
    hit.addEventListener("blur", hide);
    group.append(hit);
    return group;
  });

  return svg(
    "svg",
    { class: "viz-svg", width, height, viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": L("Posts published per week", "Posts που δημοσιεύτηκαν ανά εβδομάδα") },
    grid,
    marks,
  );
}

function weeklyTable(buckets) {
  const platforms = state.platforms.map((p) => p.key);
  return el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      { class: "data-table" },
      el("caption", { class: "sr-only", text: L("Posts published per week", "Posts που δημοσιεύτηκαν ανά εβδομάδα") }),
      el("thead", {}, el("tr", {}, el("th", { scope: "col", text: L("Week", "Εβδομάδα") }), el("th", { scope: "col", class: "num", text: L("Total", "Σύνολο") }),
        platforms.map((key) => el("th", { scope: "col", class: "num", text: labelOf(key) })))),
      el("tbody", {}, [...buckets].reverse().map((b) => el(
        "tr",
        {},
        el("th", { scope: "row", text: weekLabel(b) }),
        el("td", { class: "num", text: String(b.total) }),
        platforms.map((key) => el("td", { class: "num", text: String(b.byPlatform[key] || 0) })),
      ))),
    ),
  );
}

function weeklyCard() {
  const buckets = weeklyBuckets();
  const total = buckets.reduce((sum, b) => sum + b.total, 0);
  const head = el("div", { class: "section-head" }, el("h2", { text: L("Posts per week", "Δημοσιεύσεις ανά εβδομάδα") }), el("span", { class: "muted small", text: L("Last 12 weeks", "Τελευταίες 12 εβδομάδες") }));
  if (!total) {
    return el(
      "section",
      { class: "card" },
      head,
      el("div", { class: "empty-state" }, icon("chart"), el("p", { text: L("Nothing was published in the last 12 weeks. Once posts go out, this chart shows how many you publish each week.", "Δεν έχει δημοσιευτεί τίποτα τις τελευταίες 12 εβδομάδες. Μόλις βγουν posts, εδώ θα βλέπεις πόσα βγάζεις κάθε εβδομάδα.") })),
    );
  }
  const box = el("div", { class: "viz" });
  const tip = el("div", { class: "viz-tip", hidden: true, role: "status" });
  let showTable = false;
  const tableBox = el("div", { hidden: true });
  const toggle = el("button", { type: "button", class: "btn btn-sm btn-ghost", "aria-pressed": "false" }, ...withIcon("table", L("Table", "Πίνακας")));
  toggle.addEventListener("click", () => {
    showTable = !showTable;
    toggle.setAttribute("aria-pressed", String(showTable));
    fill(toggle, ...withIcon(showTable ? "chart" : "table", showTable ? L("Chart", "Γράφημα") : L("Table", "Πίνακας")));
    box.hidden = showTable;
    tableBox.hidden = !showTable;
    if (showTable && !tableBox.firstChild) tableBox.append(weeklyTable(buckets));
  });
  head.append(toggle);
  let drawnWidth = 0;
  const render = () => {
    drawnWidth = box.clientWidth;
    fill(box, drawWeekly(box, buckets, tip), tip);
  };
  if (chartObserver) chartObserver.disconnect();
  let frame = 0;
  chartObserver = new ResizeObserver(() => {
    cancelAnimationFrame(frame);
    // Redraw only when the width changes (the chart's own height must not trigger another pass).
    frame = requestAnimationFrame(() => { if (!box.hidden && box.clientWidth !== drawnWidth) render(); });
  });
  chartObserver.observe(box);
  return el("section", { class: "card chart-card" }, head, box, tableBox);
}

// --- share per platform, last 30 days (one hue, ranked) ---
function platformCard() {
  const since = nowSec() - 30 * 86400;
  const counts = {};
  for (const post of data.published) if (post.at >= since) counts[post.platform] = (counts[post.platform] || 0) + 1;
  const keys = new Set([...Object.keys(counts), ...state.accounts.map((a) => a.platform)]);
  const rows = [...keys].map((key) => ({ key, n: counts[key] || 0 })).sort((a, b) => b.n - a.n);
  const max = Math.max(1, ...rows.map((r) => r.n));
  return el(
    "section",
    { class: "card" },
    el("div", { class: "section-head" }, el("h2", { text: L("By platform", "Ανά πλατφόρμα") }), el("span", { class: "muted small", text: L("30 days", "30 μέρες") })),
    rows.length
      ? el("ul", { class: "meters" }, rows.map((row) => {
        const bar = el("span", { class: "meter-fill" });
        bar.style.setProperty("width", `${(row.n / max) * 100}%`);
        return el(
          "li",
          { class: "meter-row" },
          platformBadge(row.key, "sm"),
          el("span", { class: "meter-name", text: labelOf(row.key) }),
          el("span", { class: "meter-count", text: String(row.n) }),
          el("span", { class: "meter", "aria-hidden": "true" }, bar),
        );
      }))
      : el("p", { class: "muted small", text: L("No accounts yet.", "Δεν υπάρχουν λογαριασμοί ακόμα.") }),
  );
}

// --- latest results ---
function recentCard() {
  const items = data.recent.map((post) => {
    const ok = post.status === "published";
    const at = post.published_at || post.updated_at;
    return el(
      "li",
      { class: `recent-item ${ok ? "is-ok" : "is-failed"}` },
      el("span", { class: "recent-mark", title: ok ? L("Published", "Δημοσιεύτηκε") : L("Failed", "Απέτυχε") }, icon(ok ? "check" : "alert")),
      el(
        "div",
        { class: "recent-body" },
        el(
          "div",
          { class: "recent-meta" },
          platformBadge(post.platform, "xs"),
          el("strong", { text: post.account_name }),
          el("span", { class: "muted", text: ok ? fromNow(at) : L("Failed", "Απέτυχε") }),
        ),
        el("p", { class: "recent-text", text: post.text }),
      ),
      ok && post.external_url
        ? el("a", { class: "icon-link", href: post.external_url, target: "_blank", rel: "noopener noreferrer", "aria-label": L("Open on the platform", "Άνοιγμα στην πλατφόρμα"), title: L("Open on the platform", "Άνοιγμα στην πλατφόρμα") }, icon("external"))
        : !ok ? el("a", { class: "small", href: "/posts?status=failed", text: L("Details", "Λεπτομέρειες") }) : null,
    );
  });
  return el(
    "section",
    { class: "card" },
    el("div", { class: "section-head" }, el("h2", { text: L("Recent", "Πρόσφατα") }), el("a", { class: "section-link", href: "/posts", text: L("All posts", "Όλα τα posts") })),
    items.length ? el("ul", { class: "recent" }, items) : el("p", { class: "muted small", text: L("Nothing yet.", "Τίποτα ακόμα.") }),
  );
}

// --- accounts ---
function accountsCard() {
  const rows = state.accounts.map((account) => {
    let kind = "ok";
    let text = account.check.username || L("Ready", "Έτοιμο");
    if (!account.ready) {
      kind = "warn";
      text = account.problem;
    } else if (account.check.ok === false) {
      kind = "danger";
      text = L("The last check failed", "Ο τελευταίος έλεγχος απέτυχε");
    } else if (account.expires_at && account.expires_at - nowSec() < 7 * 86400) {
      kind = "warn";
      text = L(`Connection expires ${fromNow(account.expires_at)}`, `Η σύνδεση λήγει ${fromNow(account.expires_at)}`);
    }
    return el(
      "li",
      { class: "acc-row" },
      platformBadge(account.platform, "sm"),
      el("div", { class: "acc-text" }, el("strong", { text: account.name }), el("span", { class: `small status-${kind}` }, el("span", { class: "dot" }), el("span", { text }))),
    );
  });
  return el(
    "section",
    { class: "card" },
    el("div", { class: "section-head" }, el("h2", { text: L("Accounts", "Λογαριασμοί") }), el("a", { class: "section-link", href: "/settings#accounts", text: L("Manage", "Διαχείριση") })),
    rows.length
      ? el("ul", { class: "acc-list" }, rows)
      : el("div", { class: "empty-state" }, el("p", { text: L("You haven't connected an account yet.", "Δεν έχεις συνδέσει λογαριασμό ακόμα.") }), el("a", { class: "btn btn-sm", href: "/settings#accounts", text: L("Connect an account", "Σύνδεσε λογαριασμό") })),
  );
}

function render() {
  const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
  // Before the first post there is nothing to count: the first steps and the week say it all.
  fill(
    app,
    header(),
    onboarding(),
    weekView(),
    total ? kpis() : null,
    total ? el("div", { class: "grid-2-1" }, weeklyCard(), platformCard()) : null,
    total ? el("div", { class: "grid-2" }, recentCard(), accountsCard()) : state.accounts.length ? accountsCard() : null,
  );
}

async function load() {
  [state, data] = await Promise.all([api("/api/state"), api("/api/dashboard")]);
  render();
}

async function main() {
  try {
    await load();
  } catch (err) {
    app.replaceChildren(errorBox(err.message));
    return;
  }
  // Posts go out while this page is open: refresh now and then, never while the user is in a chart.
  setInterval(() => {
    if (document.hidden || app.contains(document.activeElement && document.activeElement.closest(".viz"))) return;
    load().catch(() => {});
  }, 60000);
}

main();
