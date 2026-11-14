// AI keys panel (used by the setup wizard and the settings page).
import { action, api, armed, el, guideBox, icon, L, toast } from "../common.js";

const LABELS = { anthropic: "Claude (Anthropic)", openai: "OpenAI" };
const PREFERENCES = [
  ["auto", L("Automatic (Claude if it has a key, otherwise OpenAI)", "Αυτόματα (Claude αν υπάρχει key, αλλιώς OpenAI)")],
  ["anthropic", L("Always Claude", "Πάντα Claude")],
  ["openai", L("Always OpenAI", "Πάντα OpenAI")],
];

export function renderAIPanel(root, initial, { onChange } = {}) {
  let ai = initial.ai;
  const guides = initial.ai_guides;
  let checks = {};
  const radioName = `ai-pref-${Math.random().toString(36).slice(2, 8)}`;

  const changed = () => {
    render();
    if (onChange) onChange(ai);
  };

  async function runCheck() {
    const res = await api("/api/ai/check", { method: "POST" });
    checks = res.results;
    ai = res.ai;
  }

  async function save(provider, input, button) {
    const value = input.value.trim();
    if (!value) {
      toast(L("Paste the key first.", "Επικόλλησε πρώτα το key."), "warn");
      input.focus();
      return;
    }
    await action(button, async () => {
      const res = await api("/api/ai", { method: "PUT", body: { [`${provider}_api_key`]: value } });
      ai = res.ai;
      await runCheck();
      changed();
      const result = checks[provider];
      if (result && result.ok) toast(L(`${LABELS[provider]}: working.`, `${LABELS[provider]}: δουλεύει.`), "ok");
      else if (result) toast(L(`The key was saved, but the check failed: ${result.message}`, `Το key αποθηκεύτηκε, αλλά ο έλεγχος απέτυχε: ${result.message}`), "error", 12000);
    }, L("Checking…", "Έλεγχος…"));
  }

  async function remove(provider) {
    await action(null, async () => {
      const res = await api("/api/ai", { method: "PUT", body: { [`${provider}_api_key`]: null } });
      ai = res.ai;
      delete checks[provider];
      changed();
      toast(L(`The ${LABELS[provider]} key was removed.`, `Το ${LABELS[provider]} key αφαιρέθηκε.`));
    });
  }

  async function setPreference(value) {
    await action(null, async () => {
      const res = await api("/api/ai", { method: "PUT", body: { text_provider: value } });
      ai = res.ai;
      changed();
    });
  }

  function summary() {
    const text = ai.text_provider
      ? el("div", { class: "notice notice-ok" }, icon("check"), el("span", { text: L(`Posts are written with ${LABELS[ai.text_provider]} (${ai.text_model}).`, `Τα κείμενα γράφονται με ${LABELS[ai.text_provider]} (${ai.text_model}).`) }))
      : el("div", { class: "notice notice-warn" }, icon("alert"), el("span", { text: L("No AI is set up for writing yet. Add a Claude key (recommended) or an OpenAI key.", "Δεν έχει οριστεί AI για τα κείμενα. Βάλε ένα Claude key (προτείνεται) ή ένα OpenAI key.") }));
    const images = el("p", {
      class: "small muted",
      text: ai.image_ready
        ? L(`AI images: available (${ai.image_model}).`, `Εικόνες με AI: διαθέσιμες (${ai.image_model}).`)
        : L("AI images: need an OpenAI key (optional: you can always upload your own images).", "Εικόνες με AI: χρειάζονται OpenAI key (προαιρετικό: μπορείς πάντα να ανεβάζεις δικές σου εικόνες)."),
    });
    return el("div", { class: "stack-sm" }, text, images);
  }

  function providerCard(provider) {
    const info = ai[provider];
    const guide = guides[provider];
    const fromEnv = info.source === "env";
    const input = el("input", {
      type: "password",
      class: "mono",
      autocomplete: "off",
      spellcheck: "false",
      "aria-label": `${LABELS[provider]} API key`,
      placeholder: info.set ? L(`Saved (${info.hint}). Paste a new one to change it`, `Αποθηκευμένο (${info.hint}). Επικόλλησε νέο για αλλαγή`) : provider === "anthropic" ? "sk-ant-…" : "sk-…",
    });
    const saveButton = el("button", { type: "button", class: "btn btn-primary", text: L("Save", "Αποθήκευση") });
    saveButton.addEventListener("click", () => save(provider, input, saveButton));
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        saveButton.click();
      }
    });
    const removeButton = info.source === "app"
      ? armed(el("button", { type: "button", class: "btn btn-ghost", text: L("Remove", "Αφαίρεση") }), () => remove(provider))
      : null;
    const chip = el("span", {
      class: `chip ${info.set ? "chip-ok" : "chip-muted"}`,
      text: info.set ? (fromEnv ? L("From .env", "Από το .env") : L("Saved", "Αποθηκευμένο")) : L("Not set", "Δεν έχει οριστεί"),
    });
    const check = checks[provider];
    const checkLine = check
      ? el(
        "p",
        { class: `small status-line ${check.ok ? "text-ok" : check.ok === false ? "text-danger" : "muted"}` },
        check.ok ? icon("check") : check.ok === false ? icon("alert") : null,
        el("span", { text: check.message }),
      )
      : null;
    return el(
      "section",
      { class: "subcard stack-sm" },
      el("div", { class: "subcard-head" }, el("h3", { text: guide.title }), chip),
      el("p", { class: "small muted", text: guide.summary }),
      fromEnv
        ? el("p", { class: "hint", text: L("This key comes from the .env file. To change it, edit it there and restart the app.", "Το key διαβάζεται από το αρχείο .env. Για αλλαγή, άλλαξέ το εκεί και ξεκίνα ξανά το πρόγραμμα.") })
        : el("div", { class: "input-row" }, input, saveButton, removeButton),
      checkLine,
      guideBox(guide, { open: !info.set && provider === "anthropic", label: L("How do I get the key? (step by step)", "Πώς θα βρω το key; (βήμα-βήμα)") }),
    );
  }

  function preference() {
    const both = ai.anthropic.set && ai.openai.set;
    if (!both && ai.preference === "auto") return null;
    const box = el("fieldset", { class: "fieldset" }, el("legend", { text: L("Which AI writes the posts?", "Ποιο AI γράφει τα κείμενα;") }));
    for (const [value, label] of PREFERENCES) {
      const input = el("input", {
        type: "radio",
        name: radioName,
        value,
        checked: ai.preference === value,
        disabled: ai.preference_locked,
        on: { change: () => setPreference(value) },
      });
      box.append(el("label", { class: "radio" }, input, el("span", { text: label })));
    }
    if (ai.preference_locked) box.append(el("p", { class: "hint", text: L("Set in .env (AI_TEXT_PROVIDER).", "Ορίστηκε στο .env (AI_TEXT_PROVIDER).") }));
    return box;
  }

  function checkRow() {
    if (!ai.anthropic.set && !ai.openai.set) return null;
    const button = el("button", { type: "button", class: "btn btn-sm", text: L("Check AI connection", "Έλεγχος σύνδεσης AI") });
    button.addEventListener("click", () => action(button, async () => {
      await runCheck();
      changed();
      const failed = Object.values(checks).find((c) => c.ok === false);
      toast(failed ? failed.message : L("All AI keys work.", "Όλα τα AI keys δουλεύουν."), failed ? "error" : "ok", failed ? 10000 : 4000);
    }, L("Checking…", "Έλεγχος…")));
    return el("div", { class: "row" }, button);
  }

  function render() {
    root.replaceChildren(
      el("div", { class: "stack" }, summary(), providerCard("anthropic"), providerCard("openai"), preference(), checkRow()),
    );
  }

  render();
  return { get status() { return ai; } };
}
