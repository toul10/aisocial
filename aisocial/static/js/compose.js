// "New post" page: pick accounts, let the AI write one version per platform, add an image,
// then publish now or schedule. A live preview shows each platform's post as it will look.
import {
  action, api, countChars, dayTitle, el, errorBox, field, fill, fmtDateTime, fmtTime, icon, L,
  platformBadge, plural, storage, takeParams, toast, toLocalInput, withIcon,
} from "./common.js";

const app = document.getElementById("app");
const DRAFT_KEY = "aisocial-compose-v1";
const LENGTHS = [["short", L("Short", "Σύντομο")], ["medium", L("Medium", "Μεσαίο")], ["long", L("Long", "Μεγάλο")]];
const NEED_AI_KEY = L("First add an AI key in Settings, under AI.", "Βάλε πρώτα ένα AI key στις Ρυθμίσεις, στην ενότητα AI.");

let state = null;
let platformsByKey = {};
const selected = new Set();
let drafts = {}; // platform key -> text
let image = null; // {id, url}
let length = "medium";
let mode = "now";
let imagePrompt = "";
let aiImageOpen = false;
const editors = new Map(); // platform key -> editor
const previews = new Map(); // platform key -> preview parts

let tilesBox; let topicInput; let instructionsInput; let editorsBox; let imageBox; let previewBox;
let scheduleInput; let publishButton; let summaryLine; let resultsBox;

// --- draft memory (survives a page reload) ---
let saveTimer = null;
function saveDraft() {
  clearTimeout(saveTimer);
  storage.set(DRAFT_KEY, {
    selected: [...selected],
    drafts,
    image,
    length,
    topic: topicInput ? topicInput.value : "",
    instructions: instructionsInput ? instructionsInput.value : "",
  });
}
function saveDraftSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 400);
}

// --- helpers ---
const accountById = (id) => state.accounts.find((a) => a.id === id);
const selectedAccounts = () => state.accounts.filter((a) => selected.has(a.id) && a.ready);
function selectedPlatforms() {
  const keys = new Set(selectedAccounts().map((a) => a.platform));
  return state.platforms.map((p) => p.key).filter((k) => keys.has(k));
}
const activeTopics = () => state.topics.filter((t) => t.active);
function randomTopic() {
  const topics = activeTopics();
  return topics.length ? topics[Math.floor(Math.random() * topics.length)].title : "";
}
function currentTopic(pickRandom) {
  let topic = topicInput.value.trim();
  if (!topic && pickRandom) {
    topic = randomTopic();
    topicInput.value = topic;
  }
  return topic;
}
function counterText(key, n) {
  const max = platformsByKey[key].max_chars;
  return max < 10000 ? `${n} / ${max}` : L(`${n} characters`, `${n} χαρακτήρες`);
}

function card(num, title, sub, ...content) {
  return el(
    "section",
    { class: "card" },
    el(
      "div",
      { class: "card-head" },
      num ? el("span", { class: "num", text: String(num) }) : null,
      el("h2", { text: title }),
      sub ? el("span", { class: "card-sub", text: sub }) : null,
    ),
    ...content,
  );
}

// --- 1. accounts ---
function accountsSection() {
  if (!state.accounts.length) {
    return el(
      "div",
      { class: "empty-state" },
      el("p", { text: L("You haven't connected an account yet. Connect one, then come back here.", "Δεν έχεις συνδέσει κανέναν λογαριασμό ακόμα. Σύνδεσε έναν και γύρνα εδώ.") }),
      el("a", { class: "btn btn-primary", href: "/settings#accounts", text: L("Connect an account", "Σύνδεση λογαριασμού") }),
    );
  }
  tilesBox = el("div", { class: "tiles" });
  renderTiles();
  return el(
    "div",
    { class: "stack-sm" },
    tilesBox,
    el("p", { class: "hint" }, L("Missing one? ", "Λείπει κάποιος; "), el("a", { href: "/settings#accounts", text: L("Add it in Settings", "Πρόσθεσέ τον στις Ρυθμίσεις") }), "."),
  );
}

function renderTiles() {
  fill(tilesBox, state.accounts.map((account) => {
    const checkbox = el("input", { type: "checkbox", checked: selected.has(account.id), disabled: !account.ready });
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selected.add(account.id);
      else selected.delete(account.id);
      onSelectionChange();
    });
    const label = account.name === account.platform_label ? "" : account.platform_label;
    const detail = account.ready ? account.check.username || label : account.problem;
    return el(
      "label",
      { class: `tile${selected.has(account.id) ? " selected" : ""}${account.ready ? "" : " disabled"}`, title: account.ready ? null : account.problem },
      checkbox,
      platformBadge(account.platform),
      el("span", { class: "tile-text" }, el("strong", { text: account.name }), detail ? el("span", { text: detail }) : null),
    );
  }));
}

function onSelectionChange() {
  renderTiles();
  renderEditors();
  renderSummary();
  renderPreviews();
  saveDraft();
}

// --- 2. topic ---
function topicSection() {
  topicInput = el("input", { type: "text", id: "topic", maxlength: "500", placeholder: L("Write a topic or pick one below", "Γράψε ένα θέμα ή διάλεξε από κάτω") });
  topicInput.addEventListener("input", saveDraftSoon);
  const random = el("button", { type: "button", class: "btn", title: L("A random topic from your list", "Τυχαίο θέμα από τη λίστα σου") }, ...withIcon("dice", L("Random", "Τυχαίο")));
  random.addEventListener("click", () => {
    const topic = randomTopic();
    if (!topic) return toast(L("You have no active topics. Add some in Settings, under “Business and topics”.", "Δεν έχεις ενεργά θέματα. Πρόσθεσε μερικά στις Ρυθμίσεις, στο «Επιχείρηση και θέματα»."), "warn", 8000);
    topicInput.value = topic;
    return saveDraft();
  });
  const chips = activeTopics().slice(0, 12).map((topic) => el("button", {
    type: "button",
    class: "topic-chip",
    text: topic.title,
    on: { click: () => { topicInput.value = topic.title; saveDraft(); } },
  }));
  const seg = el(
    "div",
    { class: "seg", role: "radiogroup", "aria-label": L("Length", "Μήκος") },
    LENGTHS.map(([value, label]) => el(
      "label",
      {},
      el("input", { type: "radio", name: "length", value, checked: length === value, on: { change: () => { length = value; saveDraft(); } } }),
      el("span", { text: label }),
    )),
  );
  instructionsInput = el("textarea", {
    rows: "2",
    maxlength: "1500",
    placeholder: L("e.g. Mention the 20% off offer that ends on Sunday. Close with a question.", "π.χ. Ανέφερε την προσφορά -20% μέχρι την Κυριακή. Κλείσε με μια ερώτηση."),
  });
  instructionsInput.addEventListener("input", saveDraftSoon);
  const write = el("button", { type: "button", class: "btn btn-strong btn-lg" }, ...withIcon("sparkle", L("Write with AI", "Γράψε με AI")));
  write.addEventListener("click", () => generateAll(write));
  return el(
    "div",
    { class: "stack" },
    el(
      "div",
      { class: "field" },
      el("label", { for: "topic", text: L("Topic", "Θέμα") }),
      el("div", { class: "input-row" }, topicInput, random),
      chips.length ? el("div", { class: "topic-chips" }, chips) : null,
    ),
    el("div", { class: "field" }, el("span", { class: "label", text: L("Length", "Μήκος") }), el("div", {}, seg)),
    field(L("Extra instructions (optional)", "Επιπλέον οδηγίες (προαιρετικό)"), instructionsInput),
    el("div", { class: "row" }, write),
  );
}

async function generateFor(key, topic) {
  const editor = editors.get(key);
  if (editor) editor.setBusy(true);
  try {
    const { draft } = await api("/api/generate/text", {
      method: "POST",
      body: { platform: key, topic, length, instructions: instructionsInput.value },
    });
    if (editors.get(key)) editors.get(key).set(draft.text);
    else drafts[key] = draft.text;
    saveDraft();
    if (draft.over_limit) {
      toast(L(`The text for ${platformsByKey[key].label} is over the limit. Shorten it a little before publishing.`, `Το κείμενο για ${platformsByKey[key].label} ξεπερνά το όριο. Κόψ' το λίγο πριν τη δημοσίευση.`), "warn", 9000);
    }
    return draft;
  } finally {
    if (editor) editor.setBusy(false);
  }
}

async function generateAll(button) {
  const keys = selectedPlatforms();
  if (!keys.length) return toast(L("First choose the accounts to publish to (step 1).", "Διάλεξε πρώτα σε ποιους λογαριασμούς θα δημοσιευτεί (βήμα 1)."), "warn");
  if (!state.ai.text_provider) return toast(NEED_AI_KEY, "warn", 8000);
  const topic = currentTopic(true);
  if (!topic) return toast(L("Write a topic, or add topics in Settings.", "Γράψε ένα θέμα ή πρόσθεσε θέματα στις Ρυθμίσεις."), "warn");
  return action(button, async () => {
    const results = await Promise.allSettled(keys.map((key) => generateFor(key, topic)));
    const failure = results.find((r) => r.status === "rejected");
    if (failure) toast(failure.reason.message, "error", 12000);
    else toast(L("Done. Read it and change anything you like.", "Έτοιμο. Διάβασέ το και άλλαξέ το αν θέλεις."), "ok");
  }, L("Writing…", "Γράφει…"));
}

// --- 3. text per platform ---
function makeEditor(key) {
  const platform = platformsByKey[key];
  const textarea = el("textarea", {
    rows: key === "x" ? "5" : "9",
    value: drafts[key] || "",
    placeholder: L("Press “Write with AI”, or write your own text here…", "Πάτα «Γράψε με AI» ή γράψε εδώ το δικό σου κείμενο…"),
    "aria-label": L(`Text for ${platform.label}`, `Κείμενο για ${platform.label}`),
  });
  const counter = el("span", { class: "counter", "aria-live": "polite" });
  const names = el("span", { class: "editor-names" });
  const regen = el("button", { type: "button", class: "btn btn-sm btn-ghost" }, ...withIcon("refresh", L("Rewrite", "Ξαναγράψε")));
  const root = el(
    "div",
    { class: "editor" },
    el("div", { class: "editor-head" }, platformBadge(key, "sm"), el("strong", { text: platform.label }), names, counter, regen),
    textarea,
  );
  const update = () => {
    const n = countChars(key, textarea.value);
    counter.textContent = counterText(key, n);
    counter.classList.toggle("over", n > platform.max_chars);
    names.textContent = selectedAccounts().filter((a) => a.platform === key).map((a) => a.name).join(", ");
    refreshPreview(key);
  };
  textarea.addEventListener("input", () => {
    drafts[key] = textarea.value;
    update();
    saveDraftSoon();
  });
  regen.addEventListener("click", () => {
    if (!state.ai.text_provider) return toast(NEED_AI_KEY, "warn", 8000);
    return action(regen, () => generateFor(key, currentTopic(true)), L("Writing…", "Γράφει…"));
  });
  return {
    root,
    update,
    setBusy(on) {
      root.classList.toggle("busy", on);
      textarea.disabled = on;
    },
    set(text) {
      textarea.value = text;
      drafts[key] = text;
      update();
    },
  };
}

function renderEditors() {
  const keys = selectedPlatforms();
  if (!keys.length) {
    fill(editorsBox, el("p", { class: "muted", text: L("Choose an account in step 1 first.", "Διάλεξε πρώτα λογαριασμό στο βήμα 1.") }));
    return;
  }
  fill(editorsBox, keys.map((key) => {
    if (!editors.has(key)) editors.set(key, makeEditor(key));
    const editor = editors.get(key);
    editor.update();
    return editor.root;
  }));
}

// --- 4. image ---
async function upload(file, button) {
  if (file.size > 5 * 1024 * 1024) return toast(L("The image is over 5 MB. Choose a smaller one.", "Η εικόνα είναι πάνω από 5 MB. Διάλεξε μικρότερη."), "warn");
  const form = new FormData();
  form.append("file", file);
  return action(button, async () => {
    const res = await api("/api/images", { method: "POST", form });
    image = res.image;
    saveDraft();
    renderImage();
  }, L("Uploading…", "Ανέβασμα…"));
}

function firstDraftText() {
  for (const key of selectedPlatforms()) if ((drafts[key] || "").trim()) return drafts[key].trim();
  return "";
}

function aiImagePanel() {
  if (!state.ai.image_ready) {
    return el(
      "div",
      { class: "notice notice-info" },
      icon("image"),
      el("span", {}, L("AI images need an OpenAI key. ", "Για εικόνες με AI χρειάζεται OpenAI key. "), el("a", { href: "/settings#ai", text: L("Add it in Settings", "Βάλ' το στις Ρυθμίσεις") }), "."),
    );
  }
  const prompt = el("textarea", {
    rows: "3",
    maxlength: "3000",
    value: imagePrompt,
    placeholder: L("Describe the image, e.g. “warm bread on a wooden counter, morning light”", "Περιέγραψε την εικόνα, π.χ. «ζεστό ψωμί σε ξύλινο πάγκο, πρωινό φως»"),
  });
  prompt.addEventListener("input", () => { imagePrompt = prompt.value; });
  const suggest = el("button", { type: "button", class: "btn btn-sm", text: L("Suggest a description from the text", "Πρότεινε περιγραφή από το κείμενο") });
  suggest.addEventListener("click", () => action(suggest, async () => {
    const text = firstDraftText() || topicInput.value.trim();
    if (!text) return toast(L("Write the text or a topic first.", "Γράψε πρώτα το κείμενο ή ένα θέμα."), "warn");
    const res = await api("/api/generate/image-prompt", { method: "POST", body: { text } });
    imagePrompt = res.prompt;
    prompt.value = res.prompt;
    return res;
  }, L("Thinking…", "Σκέφτεται…")));
  const make = el("button", { type: "button", class: "btn btn-strong btn-sm" }, ...withIcon("sparkle", L("Create image", "Δημιουργία εικόνας")));
  make.addEventListener("click", () => action(make, async () => {
    if (!prompt.value.trim()) return toast(L("Write a description for the image.", "Γράψε μια περιγραφή για την εικόνα."), "warn");
    const res = await api("/api/generate/image", { method: "POST", body: { prompt: prompt.value } });
    image = res.image;
    aiImageOpen = false;
    saveDraft();
    renderImage();
    return toast(L("The image is ready.", "Η εικόνα είναι έτοιμη."), "ok");
  }, L("Creating… (up to 1 minute)", "Δημιουργία… (έως 1 λεπτό)")));
  return el(
    "div",
    { class: "inset stack-sm" },
    field(L("Image description", "Περιγραφή εικόνας"), prompt),
    el("div", { class: "row" }, suggest, make),
    el("p", { class: "hint", text: L("Each image is charged to your OpenAI account.", "Κάθε εικόνα χρεώνεται στον λογαριασμό σου στο OpenAI.") }),
  );
}

function renderImage() {
  const fileInput = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif", class: "file-input", tabindex: "-1", "aria-hidden": "true" });
  const uploadButton = el("button", { type: "button", class: "btn", on: { click: () => fileInput.click() } }, ...withIcon("upload", image ? L("Change image", "Άλλη εικόνα") : L("Upload image", "Ανέβασε εικόνα")));
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) upload(file, uploadButton);
  });
  const aiButton = el("button", {
    type: "button",
    class: "btn",
    "aria-expanded": aiImageOpen ? "true" : "false",
    on: { click: () => { aiImageOpen = !aiImageOpen; renderImage(); } },
  }, ...withIcon("sparkle", L("AI image", "Εικόνα με AI")));
  const preview = image
    ? el(
      "div",
      { class: "image-preview" },
      el("img", { src: image.url, alt: L("The post's image", "Η εικόνα του post") }),
      el(
        "div",
        { class: "stack-sm" },
        el("span", { class: "small muted", text: L("Used on every account in this post.", "Μπαίνει σε όλους τους λογαριασμούς αυτής της δημοσίευσης.") }),
        el("div", {}, el("button", {
          type: "button",
          class: "btn btn-sm btn-ghost btn-danger",
          text: L("Remove image", "Αφαίρεση εικόνας"),
          on: { click: () => { image = null; saveDraft(); renderImage(); } },
        })),
      ),
    )
    : null;
  fill(
    imageBox,
    preview,
    el("div", { class: "row" }, uploadButton, aiButton, fileInput),
    aiImageOpen ? aiImagePanel() : null,
    el("p", { class: "hint", text: L("PNG, JPEG or GIF, up to 5 MB.", "PNG, JPEG ή GIF, έως 5 MB.") }),
  );
  renderPreviews();
}

// --- live preview: one mock post per platform ---
// Links, #hashtags and @mentions are tinted the way the platforms show them.
const TOKEN_RE = /https?:\/\/\S+|(^|[^\p{L}\p{N}_&/])([#@][\p{L}\p{N}_]+)/gu;

function richText(text) {
  const frag = document.createDocumentFragment();
  let pos = 0;
  for (const match of text.matchAll(TOKEN_RE)) {
    const lead = match[1] || "";
    let token = match[2] || match[0];
    if (!match[2]) while (/[.,;:!?)\]»]$/.test(token)) token = token.slice(0, -1);
    const start = match.index + lead.length;
    frag.append(text.slice(pos, start), el("span", { class: "tok", text: token }));
    pos = start + token.length;
  }
  frag.append(text.slice(pos));
  return frag;
}

function initial(name) {
  const first = [...String(name).trim()][0] || "?";
  return first.toLocaleUpperCase("el");
}

function scheduledDate() {
  if (!scheduleInput || !scheduleInput.value) return null;
  const date = new Date(scheduleInput.value);
  return Number.isFinite(date.getTime()) ? date : null;
}

function whenText() {
  if (mode !== "later") return L("Now", "Τώρα");
  const date = scheduledDate();
  return date ? `${dayTitle(date)}, ${fmtTime(date.getTime() / 1000)}` : L("Choose a time", "Διάλεξε ώρα");
}

function makePreview(key) {
  const platform = platformsByKey[key];
  const parts = {
    avatar: el("span", { class: "pv-avatar", "aria-hidden": "true" }),
    name: el("strong"),
    meta: el("span"),
    text: el("p", { class: "pv-text" }),
    media: el("div", { class: "pv-media" }),
    overText: el("span"),
    imageUrl: undefined,
  };
  parts.over = el("p", { class: "pv-over", hidden: true }, icon("alert"), parts.overText);
  parts.root = el(
    "article",
    { class: "pv", "aria-label": L(`Preview for ${platform.label}`, `Προεπισκόπηση για ${platform.label}`) },
    el("div", { class: "pv-head" }, parts.avatar, el("span", { class: "pv-who" }, parts.name, parts.meta), platformBadge(key, "sm")),
    parts.text,
    parts.media,
    parts.over,
  );
  return parts;
}

function refreshPreview(key) {
  const parts = previews.get(key);
  if (!parts) return;
  const platform = platformsByKey[key];
  const accounts = selectedAccounts().filter((a) => a.platform === key);
  const name = accounts.length ? accounts[0].name : platform.label;
  parts.avatar.textContent = initial(name);
  parts.name.textContent = accounts.length > 1 ? L(`${name} and ${accounts.length - 1} more`, `${name} και ${accounts.length - 1} ακόμα`) : name;
  parts.meta.textContent = whenText();
  const text = (drafts[key] || "").trim();
  parts.text.classList.toggle("pv-empty", !text);
  if (text) fill(parts.text, richText(text));
  else parts.text.textContent = L("The text will appear here.", "Το κείμενο θα εμφανιστεί εδώ.");
  const url = image ? image.url : null;
  if (url !== parts.imageUrl) {
    parts.imageUrl = url;
    fill(parts.media, url ? el("img", { class: "pv-img", src: url, alt: "" }) : null);
  }
  const extra = countChars(key, text) - platform.max_chars;
  parts.over.hidden = extra <= 0;
  if (extra > 0) {
    parts.overText.textContent = plural(
      extra,
      "Over the limit by {n} character.",
      "Over the limit by {n} characters.",
      "Ξεπερνά το όριο κατά {n} χαρακτήρα.",
      "Ξεπερνά το όριο κατά {n} χαρακτήρες.",
    );
  }
}

function renderPreviews() {
  if (!previewBox) return;
  const keys = selectedPlatforms();
  if (!keys.length) {
    fill(previewBox, el("p", { class: "muted small", text: L("Choose an account in step 1 to see how the post will look.", "Διάλεξε λογαριασμό στο βήμα 1 για να δεις πώς θα φαίνεται το post.") }));
    return;
  }
  fill(previewBox, keys.map((key) => {
    if (!previews.has(key)) previews.set(key, makePreview(key));
    refreshPreview(key);
    return previews.get(key).root;
  }));
}

// --- 5. publish ---
function defaultTime() {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 2);
  return d;
}
function tomorrowAt(hour) {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(hour, 0, 0, 0);
  return d;
}

/** ?at=2026-11-16T09:00 (from the home page's week) opens the page ready to schedule. */
function presetTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return date.getTime() > Date.now() + 5 * 60 * 1000 ? date : defaultTime();
}

function renderSummary() {
  const accounts = selectedAccounts();
  const names = accounts.map((a) => a.name).join(", ");
  summaryLine.textContent = accounts.length
    ? L(`Publishing to: ${names}.`, `Θα δημοσιευτεί σε: ${names}.`)
    : L("No account chosen yet.", "Δεν έχεις διαλέξει λογαριασμό.");
}

function updatePublishButton() {
  fill(publishButton, mode === "later" ? withIcon("clock", L("Schedule", "Προγραμματισμός")) : withIcon("send", L("Publish now", "Δημοσίευση τώρα")));
}

function resultLine(post) {
  let status;
  if (post.status === "published") {
    status = el(
      "span",
      { class: "status-line text-ok" },
      icon("check"),
      el("span", {}, L("Published. ", "Δημοσιεύτηκε. "), post.external_url ? el("a", { href: post.external_url, target: "_blank", rel: "noopener noreferrer", text: L("Open", "Άνοιγμα") }) : null),
    );
  } else if (post.status === "scheduled") {
    status = el("span", { class: "status-line" }, icon("clock"), el("span", { text: L(`Scheduled for ${fmtDateTime(post.scheduled_at)}.`, `Προγραμματίστηκε για ${fmtDateTime(post.scheduled_at)}.`) }));
  } else if (post.status === "failed") {
    status = el("span", { class: "status-line text-danger" }, icon("alert"), el("span", { text: L(`${post.error} You can send it again from Posts.`, `${post.error} Μπορείς να το ξαναστείλεις από τα Posts.`) }));
  } else {
    status = el("span", { text: post.status });
  }
  return el("div", { class: "result" }, platformBadge(post.platform, "sm"), el("div", { class: "stack-xs" }, el("strong", { text: post.account_name }), status));
}

function clearComposer() {
  drafts = {};
  for (const editor of editors.values()) editor.set("");
  drafts = {};
  image = null;
  imagePrompt = "";
  aiImageOpen = false;
  topicInput.value = "";
  instructionsInput.value = "";
  renderImage();
  saveDraft();
}

async function publish(button) {
  const accounts = selectedAccounts();
  if (!accounts.length) return toast(L("Choose at least one account (step 1).", "Διάλεξε τουλάχιστον έναν λογαριασμό (βήμα 1)."), "warn");
  const posts = [];
  for (const account of accounts) {
    const platform = platformsByKey[account.platform];
    const text = (drafts[account.platform] || "").trim();
    if (!text) return toast(L(`The text for ${platform.label} is missing.`, `Λείπει το κείμενο για ${platform.label}.`), "warn");
    const n = countChars(account.platform, text);
    if (n > platform.max_chars) {
      return toast(L(`The text for ${platform.label} has ${n} characters; the limit is ${platform.max_chars}.`, `Το κείμενο για ${platform.label} έχει ${n} χαρακτήρες, ενώ το όριο είναι ${platform.max_chars}.`), "warn", 9000);
    }
    posts.push({ account_id: account.id, text });
  }
  let scheduledAt = null;
  if (mode === "later") {
    if (!scheduleInput.value) return toast(L("Choose a date and time.", "Διάλεξε ημερομηνία και ώρα."), "warn");
    scheduledAt = new Date(scheduleInput.value).getTime() / 1000;
    if (!Number.isFinite(scheduledAt)) return toast(L("Invalid date.", "Μη έγκυρη ημερομηνία."), "warn");
  }
  return action(button, async () => {
    const res = await api("/api/posts", {
      method: "POST",
      body: { posts, image_id: image ? image.id : null, scheduled_at: scheduledAt },
    });
    fill(resultsBox, el(
      "div",
      { class: "result-done", role: "status" },
      res.posts.map(resultLine),
      el("a", { href: scheduledAt ? "/posts?status=scheduled" : "/posts", text: L("All posts", "Όλα τα posts") }),
    ));
    clearComposer();
    const failed = res.posts.filter((p) => p.status === "failed").length;
    if (!failed) toast(scheduledAt ? L("Scheduled.", "Προγραμματίστηκε.") : L("Published.", "Δημοσιεύτηκε."), "ok");
    else toast(failed === res.posts.length ? L("Publishing failed. See the details.", "Η δημοσίευση απέτυχε. Δες τις λεπτομέρειες.") : L("Some posts failed. See the details.", "Κάποια posts απέτυχαν. Δες τις λεπτομέρειες."), "error", 9000);
  }, scheduledAt ? L("Scheduling…", "Προγραμματισμός…") : L("Publishing…", "Δημοσίευση…"));
}

function publishSection(preset) {
  const option = (value, iconName, label) => el(
    "label",
    {},
    el("input", { type: "radio", name: "mode", value, checked: mode === value, on: { change: () => setMode(value) } }),
    el("span", {}, ...withIcon(iconName, label)),
  );
  const seg = el("div", { class: "seg seg-block", role: "radiogroup", "aria-label": L("When", "Πότε") }, option("now", "send", L("Now", "Τώρα")), option("later", "clock", L("Later", "Αργότερα")));
  scheduleInput = el("input", {
    type: "datetime-local",
    value: toLocalInput(preset || defaultTime()),
    min: toLocalInput(new Date()),
    "aria-label": L("Date and time", "Ημερομηνία και ώρα"),
  });
  scheduleInput.addEventListener("input", renderPreviews);
  const scheduleBox = el("div", { class: "stack-sm", hidden: mode !== "later" });
  function setMode(value) {
    mode = value;
    for (const input of seg.querySelectorAll("input")) input.checked = input.value === value;
    scheduleBox.hidden = value !== "later";
    updatePublishButton();
    renderPreviews();
  }
  const presets = [
    [L("In 1 hour", "Σε 1 ώρα"), () => new Date(Date.now() + 3600 * 1000)],
    [L("Tomorrow 09:00", "Αύριο 09:00"), () => tomorrowAt(9)],
    [L("Tomorrow 18:00", "Αύριο 18:00"), () => tomorrowAt(18)],
  ].map(([label, when]) => el("button", {
    type: "button",
    class: "btn btn-sm btn-ghost",
    text: label,
    on: { click: () => { scheduleInput.value = toLocalInput(when()); setMode("later"); } },
  }));
  scheduleBox.append(
    scheduleInput,
    el("div", { class: "row presets" }, presets),
    el("p", { class: "hint", text: L("AI Social must be running at that time: leave its window open and the computer on.", "Το AI Social πρέπει να τρέχει εκείνη την ώρα: άφησε το παράθυρό του ανοιχτό και τον υπολογιστή αναμμένο.") }),
  );
  publishButton = el("button", { type: "button", class: "btn btn-primary btn-lg btn-block" });
  publishButton.addEventListener("click", () => publish(publishButton));
  summaryLine = el("p", { class: "small muted" });
  resultsBox = el("div", { class: "results", "aria-live": "polite" });
  updatePublishButton();
  renderSummary();
  return el("div", { class: "stack" }, seg, scheduleBox, summaryLine, publishButton, resultsBox);
}

// --- page ---
function restore() {
  const saved = storage.get(DRAFT_KEY);
  const readyIds = state.accounts.filter((a) => a.ready).map((a) => a.id);
  if (saved && Array.isArray(saved.selected)) {
    for (const id of saved.selected) if (accountById(id) && accountById(id).ready) selected.add(id);
    drafts = saved.drafts && typeof saved.drafts === "object" ? saved.drafts : {};
    image = saved.image && saved.image.id ? saved.image : null;
    if (LENGTHS.some(([value]) => value === saved.length)) length = saved.length;
  } else {
    readyIds.forEach((id) => selected.add(id));
  }
  return saved || {};
}

async function main() {
  try {
    state = await api("/api/state");
  } catch (err) {
    fill(app, errorBox(err.message));
    return;
  }
  platformsByKey = Object.fromEntries(state.platforms.map((p) => [p.key, p]));
  const saved = restore();
  const preset = presetTime(takeParams("at").at);
  if (preset) mode = "later";

  editorsBox = el("div", { class: "stack" });
  imageBox = el("div", { class: "stack" });
  previewBox = el("div", { class: "previews" });
  const aiNotice = state.ai.text_provider
    ? null
    : el(
      "div",
      { class: "notice notice-warn" },
      icon("alert"),
      el("span", {}, L("The AI needs an AI key to write. ", "Για να γράφει το AI χρειάζεται ένα AI key. "), el("a", { href: "/settings#ai", text: L("Add it in Settings", "Βάλ' το στις Ρυθμίσεις") }), L(". Until then you can still write your own text.", ". Μέχρι τότε γράφεις μόνο δικά σου κείμενα.")),
    );
  const previewCard = card(null, L("Preview", "Προεπισκόπηση"), L("Roughly how it will look", "Έτσι περίπου θα φαίνεται"), previewBox);
  previewCard.classList.add("preview-card");

  fill(app, el(
    "div",
    { class: "stack" },
    aiNotice,
    el(
      "div",
      { class: "compose" },
      card(1, L("Where should it go out?", "Πού θα δημοσιευτεί;"), null, accountsSection()),
      card(2, L("What should the AI write?", "Τι θα γράψει το AI;"), L("A topic is enough", "Ένα θέμα αρκεί"), topicSection()),
      card(3, L("Text", "Κείμενο"), L("Edit freely before publishing", "Διόρθωσε ελεύθερα πριν τη δημοσίευση"), editorsBox),
      card(4, L("Image", "Εικόνα"), L("Optional", "Προαιρετικό"), imageBox),
      previewCard,
      card(5, L("Publish", "Δημοσίευση"), null, publishSection(preset)),
    ),
  ));
  topicInput.value = saved.topic || "";
  instructionsInput.value = saved.instructions || "";
  renderEditors();
  renderImage();
}

main();
