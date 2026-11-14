// First-run wizard: AI key, brand, social accounts, summary.
import { action, api, el, errorBox, fill, icon, L, takeParams, toast, withIcon } from "./common.js";
import { renderAccountsPanel } from "./panels/accounts.js";
import { renderAIPanel } from "./panels/ai.js";
import { renderContentPanel } from "./panels/content.js";

const STEPS = [
  { id: "ai", label: "AI", title: L("The AI that writes your posts", "AI που γράφει τα posts"), sub: L("You need an API key. Claude is the recommended choice.", "Χρειάζεσαι ένα API key. Το Claude προτείνεται για ελληνικά κείμενα.") },
  { id: "brand", label: L("Business", "Επιχείρηση"), title: L("Your business", "Η επιχείρησή σου"), sub: L("A few words about you, so the AI writes accurately and in your voice.", "Λίγα λόγια για σένα, ώστε το AI να γράφει σωστά και στο ύφος σου.") },
  { id: "accounts", label: L("Accounts", "Λογαριασμοί"), title: L("Connect social media", "Σύνδεση social media"), sub: L("Add as many accounts as you like. Each platform has a step-by-step guide.", "Πρόσθεσε όσους λογαριασμούς θέλεις. Κάθε πλατφόρμα έχει οδηγό βήμα-βήμα.") },
  { id: "done", label: L("Finish", "Τέλος"), title: L("Almost done", "Σχεδόν έτοιμο"), sub: L("Here is what is set up. Anything missing can be added later.", "Δες τι έχει ρυθμιστεί. Ό,τι λείπει το συμπληρώνεις και αργότερα.") },
];

const app = document.getElementById("app");
let state;
let current = 0;
const panes = {};
let stepper;
let body;
let nav;

function card(step, ...content) {
  return el(
    "section",
    { class: "card" },
    el("div", { class: "card-head" }, el("span", { class: "num", text: String(STEPS.indexOf(step) + 1) }), el("h2", { text: step.title })),
    el("p", { class: "card-sub", text: step.sub }),
    ...content,
  );
}

function pane(step) {
  if (step.id === "done") return doneCard(step);
  if (!panes[step.id]) {
    const box = el("div");
    if (step.id === "ai") renderAIPanel(box, state, { onChange: (ai) => { state.ai = ai; } });
    if (step.id === "brand") renderContentPanel(box, state);
    if (step.id === "accounts") renderAccountsPanel(box, state, { returnTo: "setup", onChange: (accounts) => { state.accounts = accounts; } });
    panes[step.id] = card(step, box);
  }
  return panes[step.id];
}

function doneCard(step) {
  const list = el("ul", { class: "checklist" }, el("li", { class: "muted", text: L("Checking…", "Έλεγχος…") }));
  const finish = el("button", { type: "button", class: "btn btn-primary btn-lg" }, ...withIcon("check", L("Finish setup", "Ολοκλήρωση")));
  finish.addEventListener("click", () => finishSetup(finish, "/"));
  const box = card(
    step,
    list,
    el("div", { class: "notice notice-info" }, icon("sparkle"), el("span", { text: L("Start with a test post to see that everything works, then delete it on the platform if you like.", "Κάνε πρώτα ένα δοκιμαστικό post για να δεις ότι όλα δουλεύουν, και μετά σβήσ' το από την πλατφόρμα αν θέλεις.") })),
    el("div", { class: "row" }, finish),
  );
  api("/api/state").then((fresh) => {
    state = fresh;
    list.replaceChildren(...checklist());
  }).catch((err) => list.replaceChildren(el("li", { class: "text-danger", text: err.message })));
  return box;
}

function checklist() {
  const label = { anthropic: "Claude", openai: "OpenAI" }[state.ai.text_provider];
  const ready = state.accounts.filter((a) => a.ready);
  const notReady = state.accounts.filter((a) => !a.ready);
  const active = state.topics.filter((t) => t.active).length;
  const readyNames = ready.map((a) => a.name).join(", ");
  const problems = notReady.map((a) => `${a.name} (${a.problem})`).join("; ");
  const items = [
    [label ? "ok" : "bad", label ? L(`AI for writing: ${label} (${state.ai.text_model})`, `AI για τα κείμενα: ${label} (${state.ai.text_model})`) : L("AI for writing: not set. Without it you can only write your own text.", "AI για τα κείμενα: δεν έχει οριστεί. Χωρίς αυτό γράφεις μόνο δικά σου κείμενα."), 0],
    [state.ai.image_ready ? "ok" : "opt", state.ai.image_ready ? L("AI images: available", "Εικόνες με AI: διαθέσιμες") : L("AI images: off (optional, needs an OpenAI key)", "Εικόνες με AI: όχι (προαιρετικό, χρειάζεται OpenAI key)"), 0],
    [state.content.about.trim() ? "ok" : "opt", state.content.about.trim() ? L(`Business details: ${state.content.brand_name || "filled in"}`, `Στοιχεία επιχείρησης: ${state.content.brand_name || "συμπληρώθηκαν"}`) : L("Business details: empty (1–2 sentences are recommended)", "Στοιχεία επιχείρησης: κενά (προτείνεται να γράψεις 1-2 προτάσεις)"), 1],
    [active ? "ok" : "opt", L(`Active topics: ${active}`, `Ενεργά θέματα: ${active}`), 1],
    [
      ready.length ? "ok" : "bad",
      ready.length ? L(`Accounts ready: ${readyNames}`, `Έτοιμοι λογαριασμοί: ${readyNames}`) : L("No account is ready to publish yet", "Κανένας λογαριασμός έτοιμος για δημοσίευση ακόμα"),
      2,
    ],
  ];
  if (notReady.length) items.push(["bad", L(`Need attention: ${problems}`, `Θέλουν προσοχή: ${problems}`), 2]);
  return items.map(([kind, text, step]) => el(
    "li",
    { class: kind },
    el("span", { class: "mark", "aria-hidden": "true" }, icon(kind === "ok" ? "check" : kind === "bad" ? "alert" : "minus")),
    el("span", { class: "spacer", text }),
    kind === "ok" ? null : el("button", { type: "button", class: "btn btn-sm btn-ghost", text: L("Set up", "Ρύθμιση"), on: { click: () => go(step) } }),
  ));
}

function renderStepper() {
  stepper.replaceChildren(...STEPS.map((step, index) => el(
    "button",
    {
      type: "button",
      class: `step${index < current ? " done" : ""}`,
      "aria-current": index === current ? "step" : null,
      on: { click: () => go(index) },
    },
    el("small", { text: L(`Step ${index + 1}`, `Βήμα ${index + 1}`) }),
    el("strong", {}, index < current ? icon("check") : null, el("span", { text: step.label })),
  )));
}

/** Leave the wizard for good: "/" stops redirecting here, and Settings has every step. */
function finishSetup(button, target) {
  return action(button, async () => {
    await api("/api/setup/complete", { method: "POST" });
    location.href = target;
  });
}

function renderNav() {
  let back;
  if (current > 0) {
    back = el("button", { type: "button", class: "btn btn-ghost", text: L("Back", "Πίσω"), on: { click: () => go(current - 1) } });
  } else {
    // Skipping must also end the wizard, or the home page (/) would keep sending the user back here.
    back = el("button", { type: "button", class: "btn btn-ghost", text: L("I'll do this later", "Θα το κάνω αργότερα") });
    back.addEventListener("click", () => finishSetup(back, "/settings"));
  }
  const next = current < STEPS.length - 1
    ? el("button", { type: "button", class: "btn btn-primary", text: L("Next", "Επόμενο"), on: { click: () => go(current + 1) } })
    : null;
  nav.replaceChildren(back, next || el("span"));
}

function go(index) {
  current = Math.max(0, Math.min(STEPS.length - 1, index));
  history.replaceState(null, "", `${location.pathname}#${STEPS[current].id}`);
  renderStepper();
  body.replaceChildren(pane(STEPS[current]));
  renderNav();
  window.scrollTo({ top: 0 });
}

async function main() {
  const flash = takeParams("linkedin", "linkedin_error");
  try {
    state = await api("/api/state");
  } catch (err) {
    fill(app, errorBox(err.message));
    return;
  }
  stepper = el("nav", { class: "stepper", "aria-label": L("Steps", "Βήματα") });
  body = el("div");
  nav = el("div", { class: "wizard-nav" });
  app.replaceChildren(el("div", { class: "stack" }, stepper, body, nav));
  const stepFromHash = () => STEPS.findIndex((s) => s.id === location.hash.slice(1));
  go(flash.linkedin || flash.linkedin_error ? 2 : Math.max(0, stepFromHash()));
  // A link or typed address like /setup#done changes only the hash: follow it.
  // go() uses replaceState, which does not fire hashchange, so this cannot loop.
  window.addEventListener("hashchange", () => {
    const index = stepFromHash();
    if (index >= 0 && index !== current) go(index);
  });
  if (flash.linkedin === "connected") toast(L("LinkedIn is connected.", "Το LinkedIn συνδέθηκε."), "ok", 6000);
  if (flash.linkedin_error) toast(flash.linkedin_error, "error", 15000);
}

main();
