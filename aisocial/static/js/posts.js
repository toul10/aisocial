// "Posts" page: everything scheduled or sent, grouped by day.
import {
  action, api, armed, countChars, daysFromToday, dayTitle, el, errorBox, fill, fmtDateTime, fmtTime, fromNow, icon,
  L, LOCALE, platformBadge, startOfDay, toast, toLocalInput, withIcon,
} from "./common.js";

const app = document.getElementById("app");
const FILTERS = [
  ["", L("All", "Όλα")],
  ["scheduled", L("Scheduled", "Προγραμματισμένα")],
  ["published", L("Published", "Δημοσιευμένα")],
  ["failed", L("Failed", "Αποτυχημένα")],
  ["cancelled", L("Cancelled", "Ακυρωμένα")],
];
const STATUS = {
  scheduled: [L("Scheduled", "Προγραμματισμένο"), "chip-accent"],
  publishing: [L("Publishing…", "Δημοσιεύεται…"), "chip-warn"],
  published: [L("Published", "Δημοσιεύτηκε"), "chip-ok"],
  failed: [L("Failed", "Απέτυχε"), "chip-danger"],
  cancelled: [L("Cancelled", "Ακυρώθηκε"), "chip-muted"],
};
const UPCOMING = new Set(["scheduled", "publishing"]);
const fullDay = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" });

let filter = new URLSearchParams(location.search).get("status") || "";
if (!FILTERS.some(([value]) => value === filter)) filter = "";
let posts = [];
let counts = {};
let editing = null;
const expanded = new Set(); // ids of posts whose long text is shown in full

async function load() {
  const res = await api(`/api/posts${filter ? `?status=${encodeURIComponent(filter)}` : ""}`);
  posts = res.posts;
  counts = res.counts;
  render();
}

async function run(button, task, label) {
  await action(button, async () => {
    await task();
    await load();
  }, label);
}

/** The moment a post belongs to: when it goes out, went out, failed or was cancelled. */
function postTime(post) {
  if (UPCOMING.has(post.status)) return post.scheduled_at || post.updated_at;
  if (post.status === "published") return post.published_at || post.updated_at;
  return post.updated_at;
}

function groupByDay(list, ascending) {
  const dir = ascending ? 1 : -1;
  const sorted = [...list].sort((a, b) => dir * (postTime(a) - postTime(b)) || dir * (a.id - b.id));
  const groups = [];
  for (const post of sorted) {
    const day = startOfDay(new Date(postTime(post) * 1000)).getTime();
    let group = groups[groups.length - 1];
    if (!group || group.day !== day) {
      group = { day, posts: [] };
      groups.push(group);
    }
    group.posts.push(post);
  }
  return groups;
}

function editForm(post) {
  const textarea = el("textarea", { rows: "6", value: post.text, "aria-label": L("Text", "Κείμενο") });
  const counter = el("span", { class: "counter" });
  const updateCount = () => {
    const n = countChars(post.platform, textarea.value);
    counter.textContent = post.max_chars && post.max_chars < 10000 ? `${n} / ${post.max_chars}` : L(`${n} characters`, `${n} χαρακτήρες`);
    counter.classList.toggle("over", Boolean(post.max_chars) && n > post.max_chars);
  };
  textarea.addEventListener("input", updateCount);
  updateCount();
  const original = toLocalInput(new Date(post.scheduled_at * 1000));
  const when = el("input", { type: "datetime-local", value: original, min: toLocalInput(new Date()), "aria-label": L("Publishing time", "Ώρα δημοσίευσης") });
  const save = el("button", { type: "button", class: "btn btn-primary btn-sm", text: L("Save", "Αποθήκευση") });
  save.addEventListener("click", () => run(save, async () => {
    const body = { text: textarea.value };
    if (when.value !== original) {
      body.scheduled_at = new Date(when.value).getTime() / 1000;
      if (!Number.isFinite(body.scheduled_at)) throw new Error(L("Choose a date and time.", "Διάλεξε ημερομηνία και ώρα."));
    }
    await api(`/api/posts/${post.id}`, { method: "PATCH", body });
    editing = null;
    toast(L("Saved.", "Αποθηκεύτηκε."), "ok");
  }, L("Saving…", "Αποθήκευση…")));
  // "Close without changes", not "Cancel": cancelling means cancelling the post itself.
  const close = el("button", { type: "button", class: "btn btn-ghost btn-sm", text: L("Close without changes", "Κλείσιμο χωρίς αλλαγές"), on: { click: () => { editing = null; render(); } } });
  return el(
    "div",
    { class: "stack-sm" },
    textarea,
    el("div", { class: "row" }, counter),
    el("div", { class: "field" }, el("span", { class: "label", text: L("Publishing time", "Ώρα δημοσίευσης") }), when),
    el("div", { class: "row" }, save, close),
  );
}

function actions(post) {
  const box = el("div", { class: "post-actions" });
  const publishNow = (prompt) => {
    const button = el("button", { type: "button", class: "btn btn-sm" }, ...withIcon("send", post.status === "failed" ? L("Try again", "Ξαναδοκίμασε") : L("Publish now", "Δημοσίευση τώρα")));
    return armed(button, () => run(button, async () => {
      const res = await api(`/api/posts/${post.id}/publish`, { method: "POST" });
      if (res.post.status === "published") toast(L("Published.", "Δημοσιεύτηκε."), "ok");
      else toast(res.post.error || L("Publishing failed.", "Η δημοσίευση απέτυχε."), "error", 12000);
    }, L("Publishing…", "Δημοσίευση…")), prompt);
  };
  const remove = () => {
    const button = el("button", { type: "button", class: "btn btn-sm btn-ghost btn-danger", text: L("Delete", "Διαγραφή") });
    return armed(button, () => run(button, async () => {
      await api(`/api/posts/${post.id}`, { method: "DELETE" });
      toast(post.status === "published" ? L("Removed from the list (not from the platform).", "Διαγράφηκε από τη λίστα (όχι από την πλατφόρμα).") : L("Deleted.", "Διαγράφηκε."));
    }));
  };

  if (post.status === "scheduled") {
    box.append(el("button", { type: "button", class: "btn btn-sm", on: { click: () => { editing = post.id; render(); } } }, ...withIcon("pen", L("Edit", "Επεξεργασία"))));
    box.append(publishNow(L("Sure? Click again", "Σίγουρα; Πάτα ξανά")));
    const cancel = el("button", { type: "button", class: "btn btn-sm btn-ghost btn-danger", text: L("Cancel post", "Ακύρωση") });
    box.append(armed(cancel, () => run(cancel, async () => {
      await api(`/api/posts/${post.id}/cancel`, { method: "POST" });
      toast(L("Cancelled.", "Ακυρώθηκε."));
    })));
  } else if (post.status === "failed" || post.status === "cancelled") {
    if (post.account_id) box.append(publishNow(post.status === "failed" ? L("Checked that it didn't go out? Click again", "Έλεγξες ότι δεν βγήκε; Πάτα ξανά") : L("Sure? Click again", "Σίγουρα; Πάτα ξανά")));
    box.append(remove());
  } else if (post.status === "published") {
    if (post.external_url) {
      box.append(el("a", { class: "btn btn-sm", href: post.external_url, target: "_blank", rel: "noopener noreferrer" }, ...withIcon("external", L("Open", "Άνοιγμα"))));
    }
    box.append(remove());
  }
  return box.childElementCount ? box : null;
}

/** Long texts are clamped to a few lines; the toggle appears only when something is hidden. */
function postText(post) {
  const open = expanded.has(post.id);
  const text = el("div", { class: `post-text${open ? "" : " clamp"}`, text: post.text });
  const toggle = el("button", { type: "button", class: "more-toggle", hidden: !open, "aria-expanded": open ? "true" : "false", text: open ? L("Show less", "Εμφάνιση λιγότερων") : L("Show all", "Εμφάνιση όλου") });
  toggle.addEventListener("click", () => {
    if (expanded.has(post.id)) expanded.delete(post.id);
    else expanded.add(post.id);
    const nowOpen = expanded.has(post.id);
    text.classList.toggle("clamp", !nowOpen);
    toggle.textContent = nowOpen ? L("Show less", "Εμφάνιση λιγότερων") : L("Show all", "Εμφάνιση όλου");
    toggle.setAttribute("aria-expanded", nowOpen ? "true" : "false");
  });
  return [text, toggle];
}

function checkClamps() {
  for (const text of app.querySelectorAll(".post-text")) {
    const toggle = text.nextElementSibling;
    if (!toggle || !toggle.classList.contains("more-toggle")) continue;
    toggle.hidden = text.classList.contains("clamp") && text.scrollHeight <= text.clientHeight + 1;
  }
}

function postNote(post) {
  if ((post.status === "failed" || post.status === "cancelled") && post.scheduled_at) {
    return el("p", { class: "small muted", text: L(`Was scheduled for ${fmtDateTime(post.scheduled_at)}.`, `Ήταν προγραμματισμένο για ${fmtDateTime(post.scheduled_at)}.`) });
  }
  return null;
}

function postCard(post) {
  const [label, chip] = STATUS[post.status] || [post.status, "chip-muted"];
  const ts = postTime(post);
  const isEditing = editing === post.id;
  return el(
    "article",
    { class: `post${post.status === "failed" ? " is-failed" : ""}` },
    el("div", { class: "post-time" }, fmtTime(ts), post.status === "scheduled" ? el("small", { text: fromNow(ts) }) : null),
    el(
      "div",
      { class: "post-body" },
      el(
        "div",
        { class: "post-head" },
        platformBadge(post.platform, "sm"),
        el(
          "div",
          { class: "post-who" },
          el("strong", { text: post.account_name }),
          post.account_name === post.platform_label ? null : el("span", { text: post.platform_label }),
        ),
        el("span", { class: `chip ${chip}`, text: label }),
      ),
      postNote(post),
      isEditing ? editForm(post) : postText(post),
      post.image_url
        ? el("a", { href: post.image_url, target: "_blank", rel: "noopener noreferrer" }, el("img", { class: "post-thumb", src: post.image_url, alt: L("The post's image", "Εικόνα του post"), loading: "lazy" }))
        : null,
      post.error
        ? el("div", { class: `notice ${post.status === "failed" ? "notice-danger" : "notice-warn"}` }, icon("alert"), el("span", { text: post.error }))
        : null,
      isEditing ? null : actions(post), // the edit form has its own buttons
    ),
  );
}

function dayGroup(group, heading) {
  const date = new Date(group.day);
  const relative = Math.abs(daysFromToday(date)) <= 1; // "Today" and friends also get the date itself
  return el(
    "section",
    { class: "day-group" },
    el(heading, { class: "day-title" }, dayTitle(date), relative ? el("span", { class: "muted", text: fullDay.format(date) }) : null),
    group.posts.map(postCard),
  );
}

function postSection(title, sub, groups) {
  return el(
    "section",
    { class: "post-section" },
    el("div", { class: "section-head" }, el("h2", { text: title }), el("span", { class: "card-sub", text: sub })),
    groups.map((group) => dayGroup(group, "h3")),
  );
}

function emptyState() {
  return el(
    "div",
    { class: "card empty-state" },
    icon("calendar"),
    el("p", { text: filter ? L("No posts with this status.", "Δεν υπάρχουν posts σε αυτή την κατηγορία.") : L("No posts yet. Write your first one and it will show up here.", "Δεν έχεις κάνει posts ακόμα. Γράψε το πρώτο σου και θα εμφανιστεί εδώ.") }),
    el("a", { class: "btn btn-primary", href: "/new" }, ...withIcon("pen", L("New post", "Νέο post"))),
  );
}

function listView() {
  if (!posts.length) return emptyState();
  if (filter) {
    return el("div", { class: "post-list" }, groupByDay(posts, filter === "scheduled").map((group) => dayGroup(group, "h2")));
  }
  const upcoming = posts.filter((p) => UPCOMING.has(p.status));
  const past = posts.filter((p) => !UPCOMING.has(p.status));
  return el(
    "div",
    { class: "post-list" },
    upcoming.length ? postSection(L("Scheduled", "Προγραμματισμένα"), L("In the order they go out", "Με τη σειρά που θα βγουν"), groupByDay(upcoming, true)) : null,
    past.length ? postSection(L("History", "Ιστορικό"), L("Newest first", "Τα πιο πρόσφατα πρώτα"), groupByDay(past, false)) : null,
  );
}

function render() {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const filters = el("div", { class: "filters", role: "group", "aria-label": L("Filter", "Φίλτρο") }, FILTERS.map(([value, label]) => {
    const n = value ? counts[value] || 0 : total;
    return el(
      "button",
      {
        type: "button",
        "aria-pressed": filter === value ? "true" : "false",
        on: {
          click: () => {
            filter = value;
            editing = null;
            history.replaceState(null, "", value ? `?status=${value}` : location.pathname);
            load().catch((err) => toast(err.message, "error"));
          },
        },
      },
      label,
      el("span", { class: "count", text: String(n) }),
    );
  }));
  fill(app, filters, listView());
  requestAnimationFrame(checkClamps);
}

async function main() {
  try {
    await load();
  } catch (err) {
    fill(app, errorBox(err.message));
    return;
  }
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(checkClamps, 150);
  });
  setInterval(() => {
    // Never refresh under the user's hands: while editing, or while a button waits for its second click.
    const waiting = app.querySelector(".armed, [aria-busy='true']");
    if (!document.hidden && editing === null && !waiting) load().catch(() => {});
  }, 15000);
}

main();
