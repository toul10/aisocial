// Settings page: AI, accounts, brand & topics, system info.
import { api, el, errorBox, fill, L, languagePicker, takeParams, toast } from "./common.js";
import { renderAccountsPanel } from "./panels/accounts.js";
import { renderAIPanel } from "./panels/ai.js";
import { renderContentPanel } from "./panels/content.js";

const app = document.getElementById("app");

function section(id, title, sub) {
  const body = el("div");
  const card = el(
    "section",
    { class: "card", id },
    el("div", { class: "card-head" }, el("h2", { text: title }), sub ? el("span", { class: "card-sub", text: sub }) : null),
    body,
  );
  return { card, body };
}

function systemInfo(state) {
  return el(
    "div",
    { class: "stack-sm" },
    el(
      "dl",
      { class: "facts" },
      el("dt", { text: L("Address", "Διεύθυνση") }),
      el("dd", {}, el("code", { text: state.public_url })),
      el("dt", { text: L("Version", "Έκδοση") }),
      el("dd", { text: state.version }),
    ),
    el("p", { class: "small muted", text: L("Scheduled posts go out only while AI Social is running. If the app was closed at that time, the post is marked “Failed” and you can send it again with one click from Posts.", "Τα προγραμματισμένα posts δημοσιεύονται μόνο όσο τρέχει το AI Social. Αν το πρόγραμμα ήταν κλειστό εκείνη την ώρα, το post σημειώνεται «Απέτυχε» και το ξαναστέλνεις με ένα κλικ από τα Posts.") }),
    el("p", { class: "small muted", text: L("Keys and tokens are stored encrypted, only on this computer (the instance/ folder). For a backup, keep a copy of the .env file together with the instance/ folder.", "Τα keys και τα tokens αποθηκεύονται κρυπτογραφημένα μόνο σε αυτόν τον υπολογιστή (φάκελος instance/). Για backup κράτα αντίγραφο του αρχείου .env μαζί με τον φάκελο instance/.") }),
    state.password_protected ? el("p", { class: "small muted", text: L("Access is protected by a password (AISOCIAL_PASSWORD).", "Η πρόσβαση προστατεύεται με κωδικό (AISOCIAL_PASSWORD).") }) : null,
    el("div", { class: "row" }, el("a", { class: "btn btn-sm", href: "/setup", text: L("Open the setup guide", "Άνοιγμα οδηγού εγκατάστασης") })),
  );
}

async function main() {
  const flash = takeParams("linkedin", "linkedin_error");
  let state;
  try {
    state = await api("/api/state");
  } catch (err) {
    fill(app, errorBox(err.message));
    return;
  }
  const ai = section("ai", "AI", L("Which AI writes your posts and makes images.", "Ποιο AI γράφει τα κείμενα και φτιάχνει εικόνες."));
  const accounts = section("accounts", L("Social media accounts", "Λογαριασμοί social media"), L("Where AI Social can publish.", "Πού μπορεί να δημοσιεύει το AI Social."));
  const content = section("content", L("Business and topics", "Επιχείρηση και θέματα"), L("What the AI reads before it writes.", "Αυτά διαβάζει το AI πριν γράψει."));
  const language = section("language", L("Language", "Γλώσσα"), L("For menus, buttons and messages.", "Για μενού, κουμπιά και μηνύματα."));
  language.body.append(el(
    "div",
    { class: "stack-sm" },
    languagePicker({ anchor: "language" }),
    el("p", {
      class: "hint",
      text: L(
        "The language your posts are written in is a separate setting: “Post language”, under Business and topics.",
        "Η γλώσσα που γράφονται τα posts είναι ξεχωριστή ρύθμιση: «Γλώσσα των posts», στο Επιχείρηση και θέματα.",
      ),
    }),
  ));
  const system = section("system", L("System", "Σύστημα"));
  renderAIPanel(ai.body, state);
  renderAccountsPanel(accounts.body, state, { returnTo: "settings" });
  renderContentPanel(content.body, state);
  system.body.append(systemInfo(state));
  app.replaceChildren(ai.card, accounts.card, content.card, language.card, system.card);

  if (flash.linkedin === "connected") toast(L("LinkedIn is connected.", "Το LinkedIn συνδέθηκε."), "ok", 6000);
  if (flash.linkedin_error) toast(flash.linkedin_error, "error", 15000);
  const target = location.hash ? document.getElementById(location.hash.slice(1)) : null;
  if (target) target.scrollIntoView();
}

main();
