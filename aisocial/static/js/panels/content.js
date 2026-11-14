// Brand details (what the AI knows about you) and the list of post topics.
import { action, api, el, field, fill, icon, L, LANG, plural, toast, withIcon } from "../common.js";

export function renderContentPanel(root, initial, { onChange } = {}) {
  let topics = initial.topics;
  let suggestions = null; // [{title, checked}]
  const content = initial.content;

  // --- brand form (rendered once, so typing is never interrupted) ---
  const brandName = el("input", { type: "text", maxlength: "100", value: content.brand_name, placeholder: L("e.g. Riverside Bakery", "π.χ. Φούρνος Παπαδόπουλου") });
  const about = el("textarea", {
    rows: "3",
    maxlength: "1500",
    value: content.about,
    placeholder: L("e.g. A family bakery in Thessaloniki since 1985. Sourdough bread, pastries and catering for events.", "π.χ. Οικογενειακός φούρνος στη Θεσσαλονίκη από το 1985. Προζυμένιο ψωμί, γλυκά και κεράσματα για εκδηλώσεις."),
  });
  const voice = el("textarea", { rows: "7", maxlength: "4000", value: content.brand_voice });
  const language = el("input", { type: "text", maxlength: "40", value: content.language, placeholder: L("Same as the topic", "Ίδια με το θέμα"), list: "language-options" });
  const choices = LANG === "el" ? ["Ελληνικά", "English", "Ελληνικά και English"] : ["English", "Greek", "English and Greek"]; // i18n-data
  const languages = el("datalist", { id: "language-options" }, choices.map((l) => el("option", { value: l })));
  const saveBrand = el("button", { type: "button", class: "btn btn-primary", text: L("Save", "Αποθήκευση") });
  saveBrand.addEventListener("click", () => action(saveBrand, async () => {
    await api("/api/content", {
      method: "PUT",
      body: { brand_name: brandName.value, about: about.value, brand_voice: voice.value, language: language.value },
    });
    toast(L("Saved. The AI will write based on this.", "Αποθηκεύτηκε. Το AI θα γράφει με βάση αυτά."), "ok");
    if (onChange) onChange();
  }, L("Saving…", "Αποθήκευση…")));

  const brand = el(
    "div",
    { class: "stack" },
    field(L("Business or brand name", "Όνομα επιχείρησης ή brand"), brandName),
    field(L("What you do or sell", "Τι κάνεις / τι πουλάς"), about, L("A few sentences. The AI uses them to write accurately about you without making things up.", "Λίγες προτάσεις. Το AI τις χρησιμοποιεί για να γράφει σωστά για σένα και να μην επινοεί πράγματα.")),
    field(L("Writing style", "Ύφος γραφής"), voice, L("How your posts should sound. Change the rules as you like.", "Πώς θέλεις να «ακούγονται» τα posts. Άλλαξε ελεύθερα τους κανόνες.")),
    field(L("Post language", "Γλώσσα των posts"), language, L("Leave empty to write in the language of the topic.", "Κενό = στη γλώσσα που είναι γραμμένο το θέμα.")),
    languages,
    el("div", { class: "row" }, saveBrand),
  );

  // --- topics ---
  const topicsBox = el("div", { class: "stack-sm" });

  async function setTopics(promise) {
    const res = await promise;
    topics = res.topics;
    renderTopics();
    if (onChange) onChange();
    return res;
  }

  function renderTopics() {
    const list = topics.length
      ? el("div", { class: "topic-list" }, topics.map((topic) => {
        const toggle = el("input", {
          type: "checkbox",
          checked: topic.active,
          "aria-label": L("Active", "Ενεργό"),
          on: {
            change: () => action(null, () => setTopics(api(`/api/topics/${topic.id}`, { method: "PATCH", body: { active: toggle.checked } }))),
          },
        });
        const remove = el("button", {
          type: "button",
          class: "btn btn-sm btn-ghost",
          "aria-label": L(`Delete topic: ${topic.title}`, `Διαγραφή θέματος: ${topic.title}`),
          title: L("Delete", "Διαγραφή"),
          on: { click: () => action(remove, () => setTopics(api(`/api/topics/${topic.id}`, { method: "DELETE" }))) },
        }, icon("close"));
        return el("div", { class: "topic-row" }, el("label", { class: "check spacer" }, toggle, el("span", { class: topic.active ? "" : "muted", text: topic.title })), remove);
      }))
      : el("p", { class: "muted small", text: L("No topics yet.", "Δεν υπάρχουν θέματα ακόμα.") });

    const input = el("input", { type: "text", maxlength: "200", placeholder: L("e.g. Tips for keeping bread fresh", "π.χ. Συμβουλές για τη συντήρηση του ψωμιού") });
    const add = el("button", { type: "button", class: "btn", text: L("Add", "Προσθήκη") });
    const addTopic = () => {
      if (!input.value.trim()) return input.focus();
      return action(add, async () => {
        const res = await setTopics(api("/api/topics", { method: "POST", body: { title: input.value } }));
        if (!res.added) toast(L("That topic already exists.", "Αυτό το θέμα υπάρχει ήδη."), "warn");
      });
    };
    add.addEventListener("click", addTopic);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addTopic();
      }
    });

    const suggest = el("button", { type: "button", class: "btn" }, ...withIcon("sparkle", L("Suggest topics with AI", "Πρότεινε θέματα με AI")));
    suggest.addEventListener("click", () => action(suggest, async () => {
      const res = await api("/api/generate/topics", { method: "POST", body: { count: 8 } });
      suggestions = res.topics.map((title) => ({ title, checked: true }));
      if (!suggestions.length) toast(L("No new topics found. Try again.", "Δεν βρέθηκαν νέα θέματα. Δοκίμασε ξανά."), "warn");
      renderTopics();
    }, L("Thinking…", "Σκέφτεται…")));

    fill(
      topicsBox,
      el("p", { class: "hint", text: L("When you leave the topic empty, the AI picks one of the active topics. Untick any you don't want for now.", "Το AI διαλέγει από τα ενεργά θέματα όταν δεν γράψεις δικό σου. Ξετσέκαρε όσα δεν θέλεις προς το παρόν.") }),
      list,
      el("div", { class: "input-row" }, input, add),
      el("div", { class: "row" }, suggest),
      suggestions && suggestions.length ? suggestionsBox() : null,
    );
  }

  function suggestionsBox() {
    const addSelected = el("button", { type: "button", class: "btn btn-primary btn-sm", text: L("Add selected", "Προσθήκη επιλεγμένων") });
    addSelected.addEventListener("click", () => action(addSelected, async () => {
      const titles = suggestions.filter((s) => s.checked).map((s) => s.title);
      if (!titles.length) return toast(L("You haven't selected any topic.", "Δεν διάλεξες κανένα θέμα."), "warn");
      suggestions = null;
      const res = await setTopics(api("/api/topics", { method: "POST", body: { titles } }));
      toast(plural(res.added, "Added {n} topic.", "Added {n} topics.", "Προστέθηκε {n} θέμα.", "Προστέθηκαν {n} θέματα."), "ok");
    }));
    const dismiss = el("button", { type: "button", class: "btn btn-ghost btn-sm", text: L("Close", "Κλείσιμο"), on: { click: () => { suggestions = null; renderTopics(); } } });
    return el(
      "div",
      { class: "inset stack-sm" },
      el("strong", { text: L("AI suggestions", "Προτάσεις AI") }),
      suggestions.map((s) => el(
        "label",
        { class: "check" },
        el("input", { type: "checkbox", checked: s.checked, on: { change: (e) => { s.checked = e.target.checked; } } }),
        el("span", { text: s.title }),
      )),
      el("div", { class: "row" }, addSelected, dismiss),
    );
  }

  renderTopics();
  root.replaceChildren(
    el("div", { class: "stack" }, brand, el("div", { class: "stack-sm" }, el("h3", { text: L("Post topics", "Θέματα για posts") }), topicsBox)),
  );
}
