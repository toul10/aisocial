// Social accounts panel: add, edit, verify, connect (LinkedIn OAuth) and delete.
import { action, api, armed, el, field, fmtDateTime, fromNow, guideBox, icon, L, platformBadge, plural, toast } from "../common.js";

const WEEK = 7 * 86400;

export function renderAccountsPanel(root, initial, { returnTo = "settings", onChange } = {}) {
  let accounts = initial.accounts;
  const platforms = Object.fromEntries(initial.platforms.map((p) => [p.key, p]));
  let adding = null; // platform key of the open "add account" form
  let editing = null; // id of the account being edited

  const changed = () => {
    render();
    if (onChange) onChange(accounts);
  };

  async function reload() {
    accounts = (await api("/api/accounts")).accounts;
  }

  const connectHref = (account) => `${account.connect_url}?return=${encodeURIComponent(returnTo)}`;

  async function verify(account, button, quiet = false) {
    await action(button, async () => {
      const res = await api(`/api/accounts/${account.id}/verify`, { method: "POST" });
      await reload();
      changed();
      if (res.verified) toast(res.message, "ok");
      else if (!quiet) toast(res.message, "error", 12000);
      else toast(L(`Saved, but the check failed: ${res.message}`, `Αποθηκεύτηκε, αλλά ο έλεγχος απέτυχε: ${res.message}`), "error", 12000);
    }, L("Checking…", "Έλεγχος…"));
  }

  async function remove(account) {
    await action(null, async () => {
      const res = await api(`/api/accounts/${account.id}`, { method: "DELETE" });
      await reload();
      changed();
      toast(res.cancelled
        ? plural(
          res.cancelled,
          "The account was deleted. {n} scheduled post was cancelled.",
          "The account was deleted. {n} scheduled posts were cancelled.",
          "Ο λογαριασμός διαγράφηκε. Ακυρώθηκε {n} προγραμματισμένο post.",
          "Ο λογαριασμός διαγράφηκε. Ακυρώθηκαν {n} προγραμματισμένα posts.",
        )
        : L("The account was deleted.", "Ο λογαριασμός διαγράφηκε."));
    });
  }

  function statusLine(account) {
    const parts = [];
    if (!account.ready) {
      parts.push(el("span", { class: "small status-line text-warn" }, icon("alert"), el("span", { text: account.problem })));
    } else if (account.check.ok === false) {
      parts.push(el("span", { class: "small status-line text-danger" }, icon("alert"), el("span", { text: account.check.message })));
    } else if (account.check.ok === true) {
      parts.push(el("span", { class: "small status-line text-ok" }, icon("check"), el("span", { text: L("Ready to publish", "Έτοιμο για δημοσίευση") })));
      const details = [
        account.check.username,
        account.check.checked_at ? L(`checked ${fromNow(account.check.checked_at)}`, `ελέγχθηκε ${fromNow(account.check.checked_at)}`) : null,
      ].filter(Boolean).join(", ");
      if (details) parts.push(el("span", { class: "small muted", text: details }));
    } else {
      parts.push(el("span", { class: "small muted", text: L("Not checked yet. Press “Check”.", "Δεν έχει ελεγχθεί ακόμα. Πάτα «Έλεγχος».") }));
    }
    if (account.oauth && account.connected && account.expires_at) {
      const soon = account.expires_at - Date.now() / 1000 < WEEK;
      parts.push(el("span", {
        class: `small ${soon ? "text-warn" : "muted"}`,
        text: L(`The connection expires on ${fmtDateTime(account.expires_at)}${soon ? ". Press “Reconnect”." : ""}`, `Η σύνδεση λήγει ${fmtDateTime(account.expires_at)}${soon ? ". Πάτα «Επανασύνδεση»." : ""}`),
      }));
    }
    return parts;
  }

  function accountRow(account) {
    const actions = el("div", { class: "row-actions" });
    if (account.oauth) {
      actions.append(el("a", {
        class: `btn btn-sm${account.connected ? "" : " btn-primary"}`,
        href: connectHref(account),
        text: account.connected ? L("Reconnect", "Επανασύνδεση") : L(`Connect ${account.platform_label}`, `Σύνδεση ${account.platform_label}`),
      }));
    }
    if (!account.oauth || account.connected) {
      const check = el("button", { type: "button", class: "btn btn-sm", text: L("Check", "Έλεγχος") });
      check.addEventListener("click", () => verify(account, check));
      actions.append(check);
    }
    actions.append(el("button", {
      type: "button",
      class: "btn btn-sm btn-ghost",
      text: editing === account.id ? L("Close", "Κλείσιμο") : L("Edit", "Επεξεργασία"),
      on: { click: () => { editing = editing === account.id ? null : account.id; adding = null; render(); } },
    }));
    actions.append(armed(el("button", { type: "button", class: "btn btn-sm btn-ghost btn-danger", text: L("Delete", "Διαγραφή") }), () => remove(account)));
    return el(
      "div",
      { class: "account" },
      el(
        "div",
        { class: "account-head" },
        platformBadge(account.platform),
        el(
          "div",
          { class: "account-info" },
          el("strong", { text: account.name }),
          account.name === account.platform_label ? null : el("span", { class: "small muted", text: account.platform_label }),
          statusLine(account),
        ),
        actions,
      ),
      editing === account.id ? accountForm(platforms[account.platform], account) : null,
    );
  }

  function accountForm(platform, account) {
    const nameInput = el("input", { type: "text", maxlength: "80", value: account ? account.name : "", placeholder: platform.label });
    const inputs = {};
    const fields = platform.fields.map((f) => {
      const saved = account ? account.fields[f.name] : null;
      const input = el("input", {
        type: f.secret ? "password" : "text",
        class: "mono",
        autocomplete: "off",
        spellcheck: "false",
        value: !f.secret && saved && saved.value ? saved.value : "",
        placeholder: f.secret && saved && saved.set ? L(`Saved (${saved.hint}). Leave empty to keep it`, `Αποθηκευμένο (${saved.hint}). Άφησέ το κενό για να μείνει`) : f.placeholder || "",
      });
      inputs[f.name] = input;
      return field(f.label, input);
    });
    const saveButton = el("button", { type: "button", class: "btn btn-primary", text: account ? L("Save changes", "Αποθήκευση αλλαγών") : L("Save", "Αποθήκευση") });
    const cancel = el("button", {
      type: "button",
      class: "btn btn-ghost",
      text: L("Cancel", "Άκυρο"),
      on: { click: () => { adding = null; editing = null; render(); } },
    });

    saveButton.addEventListener("click", () => action(saveButton, async () => {
      const credentials = {};
      for (const [name, input] of Object.entries(inputs)) if (input.value.trim()) credentials[name] = input.value.trim();
      const body = { name: nameInput.value.trim(), credentials };
      const res = account
        ? await api(`/api/accounts/${account.id}`, { method: "PUT", body })
        : await api("/api/accounts", { method: "POST", body: { ...body, platform: platform.key } });
      adding = null;
      editing = null;
      await reload();
      changed();
      const saved = res.account;
      if (saved.oauth && !saved.ready) {
        const button = saved.connected ? L("Reconnect", "Επανασύνδεση") : L(`Connect ${saved.platform_label}`, `Σύνδεση ${saved.platform_label}`);
        toast(L(`Saved. Now press “${button}”.`, `Αποθηκεύτηκε. Τώρα πάτα «${button}».`), "ok", 8000);
      } else if (saved.ready) {
        toast(L("Saved. Checking…", "Αποθηκεύτηκε. Γίνεται έλεγχος…"));
        await verify(saved, null, true);
      }
    }, L("Saving…", "Αποθήκευση…")));

    return el(
      "div",
      { class: "subcard stack" },
      el("div", { class: "subcard-head" }, el("h3", { text: account ? L(`Edit: ${account.name}`, `Επεξεργασία: ${account.name}`) : L(`New ${platform.label} account`, `Νέος λογαριασμός ${platform.label}`) })),
      platform.guide ? el("p", { class: "small muted", text: platform.guide.summary }) : null,
      guideBox(platform.guide, { open: !account }),
      field(L("Name (to tell it apart)", "Όνομα (για να τον ξεχωρίζεις)"), nameInput),
      fields,
      account && platform.oauth ? el("p", { class: "hint", text: L("If you change the Client ID you will need to connect again.", "Αν αλλάξεις Client ID θα χρειαστεί νέα σύνδεση.") }) : null,
      el("div", { class: "row" }, saveButton, cancel),
    );
  }

  function render() {
    const list = accounts.length
      ? el("div", { class: "account-list" }, accounts.map(accountRow))
      : el("p", { class: "muted", text: L("You haven't added any accounts yet. Choose a platform:", "Δεν έχεις προσθέσει λογαριασμούς ακόμα. Διάλεξε πλατφόρμα:") });
    const addRow = el(
      "div",
      { class: "add-row" },
      el("span", { class: "label", text: accounts.length ? L("Add another:", "Πρόσθεσε κι άλλο:") : L("Add:", "Πρόσθεσε:") }),
      initial.platforms.map((p) => el(
        "button",
        {
          type: "button",
          class: `btn${adding === p.key ? " btn-primary" : ""}`,
          "aria-expanded": adding === p.key ? "true" : "false",
          on: { click: () => { adding = adding === p.key ? null : p.key; editing = null; render(); } },
        },
        platformBadge(p.key),
        p.label,
      )),
    );
    root.replaceChildren(el("div", { class: "stack" }, list, addRow, adding ? accountForm(platforms[adding], null) : null));
  }

  render();
  return { get accounts() { return accounts; } };
}
