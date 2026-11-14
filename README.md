# AI Social

**English** | [Ελληνικά](README.el.md)

A small app that runs **on your own computer**. Connect **X (Twitter)**, **LinkedIn** and a **Facebook Page**,
let the AI write the posts (and, if you like, make an image), then publish them right away or schedule them for later.

- The AI writes **one version per platform** (short for X, more detailed for LinkedIn, and so on), in your
  business's voice. You edit it freely before it goes out.
- Topics: write your own, pick one from your list, or take a random one. The AI can also suggest new topics.
- Images: upload your own, or let the AI make one (needs an OpenAI key).
- A home page with your week ahead, how much you published and anything that needs attention.
- Scheduling by date and time, a history of every post, and retry with one click.
- English or Greek interface.
- API keys and tokens are stored **encrypted**, only on your computer.

---

## Quick start

1. Install **Python 3.10 or newer** (free, see below).
2. Start the app:
   - **macOS:** double-click `start.command`
   - **Windows:** double-click `start.bat`
   - **Linux:** `./start.sh`
3. Your browser opens **http://localhost:5050** with the **setup wizard**.

The first start takes 1-3 minutes and needs internet: it creates a private Python environment (`.venv`),
downloads the libraries and writes a `.env` file with a random encryption key. After that it starts in a few seconds.

**Leave the window that opens (the terminal) open.** The app runs as long as it is open. To stop it, press
`Ctrl+C` or close the window. The messages in that window are mostly in Greek for now.

---

## 1. Install Python (once)

| System | What to do |
|---|---|
| **macOS** | Download the installer from https://www.python.org/downloads/ and run it. With Homebrew: `brew install python`. |
| **Windows** | Download it from https://www.python.org/downloads/. On the installer's first screen **tick "Add python.exe to PATH"**. |
| **Linux (Ubuntu/Debian)** | `sudo apt install python3 python3-venv` |

The Python that comes with macOS (3.9) is too old. `start.command` skips it and looks for a newer one.

## 2. First start

- **macOS:** double-click `start.command`. If macOS says it cannot open a file from an unidentified developer:
  **right-click → Open → Open** (once), or System Settings → Privacy & Security → "Open Anyway". If you see
  "permission denied", open Terminal in the folder and run `chmod +x start.command start.sh`.
- **Windows:** double-click `start.bat`. If "Windows protected your PC" appears: **More info → Run anyway**.
- **Linux:** `./start.sh` (or `python3 start.py`). For a server without a browser: `python3 start.py --no-browser`.

If the browser does not open by itself, open **http://localhost:5050** yourself.

## 3. Setup wizard (in the browser)

The app opens in **English**. For Greek, choose **Ελληνικά** on the wizard's first screen, or later in
**Settings → Language**.

The wizard has 4 steps. Anything you skip can be done later in **Settings**.

1. **AI:** paste an API key. **Claude (Anthropic)** is recommended for writing. **OpenAI** is needed only for
   AI images (or if you prefer it for writing too). **Save** also checks that the key works.
2. **Business:** your business name, what you do or sell, your writing style, the post language, and your list
   of post topics.
3. **Accounts:** add X, LinkedIn or a Facebook Page. Each platform has a step-by-step guide inside the app (and
   further down in this file).
4. **Finish:** a list of what is ready and what is missing. **Finish setup** takes you to the home page.

---

## AI keys

### Claude (Anthropic), recommended for writing
1. https://platform.claude.com → sign up or log in.
2. Settings → **Billing**: add a few credits (for example $5). A post usually costs a few cents.
3. Settings → **API keys** → "Create key".
4. Copy the key (it starts with `sk-ant-`) and paste it into AI Social. It is shown only once.

Default model: `claude-opus-5-5` with low effort (fast and cheaper). You can change it in `.env`.
If Claude declines a topic for safety reasons, the Anthropic API automatically retries on its recommended
fallback model (server-side fallback).

### OpenAI, for AI images (and as an alternative for writing)
1. https://platform.openai.com → log in.
2. Settings → **Billing**: add credits.
3. For images: Settings → Organization → General → **Verify Organization** (OpenAI requires it for its image models).
4. https://platform.openai.com/api-keys → "Create new secret key" → paste it into AI Social.

Each image is charged to your OpenAI account. You can always upload your own images for free.

---

## Connecting accounts

In **Settings → Accounts** (or step 3 of the wizard), choose the platform after **Add:**. The form shows the same
guide as below, under **Step-by-step guide**.

### X (Twitter), about 10 minutes
1. https://developer.x.com → log in with the account that will post. If asked, create a developer account and
   describe the use briefly (for example "Publishing my business's posts").
2. Developer Portal → open your App (or create a new App inside a Project).
3. App → **User authentication settings → Set up**: App permissions = **Read and write**, Type of App =
   "Web App, Automated App or Bot", Callback URI = `http://localhost:5050`, Website URL = your website (or
   `https://example.com`). Save.
4. App → **Keys and tokens → API Key and Secret → Regenerate**. Copy the API Key and the API Key Secret.
5. In the same place → **Access Token and Secret → Generate**. It must say **"Read and Write"**. If it says only
   "Read", press Regenerate (the token was made before step 3).
6. Paste the 4 keys into AI Social → **Save** (this also runs a check).

X charges for API use. If a post fails with error 402 or 403 about credits, add credits or pick a plan in the
developer portal.

### LinkedIn (personal profile), about 10 minutes
1. https://www.linkedin.com/developers/apps → **Create app**.
2. App name, LinkedIn Page, logo, accept the terms. LinkedIn asks for a **Company Page**: if you do not have one,
   create a simple one with "Create a LinkedIn Page".
3. **Products** tab: add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect** (approved instantly).
4. **Auth** tab → **Authorized redirect URLs → Add redirect URL** and enter **exactly**:
   `http://localhost:5050/oauth/linkedin/callback`
   (AI Social shows it with a **Copy** button).
5. On the same tab, copy the **Client ID** and the **Primary Client Secret** → paste them into AI Social → **Save**.
6. Press **Connect LinkedIn**, log in and approve. You come back to AI Social automatically.

The connection lasts **60 days**. After that, press **Reconnect** (the app warns you a week before it expires, and it
will not let you schedule a post for after the expiry). Posts go to your **personal profile**. Posting as a Company
Page needs special approval from LinkedIn (Community Management API), which is not supported.

### Facebook Page, about 15 minutes
You need a **Page** (not a personal profile) that you manage.
1. https://developers.facebook.com/apps → **Create App**. Choose the use case for managing a Page (for example
   "Manage everything on your Page"), or "Other" → "Business".
2. Open the **Graph API Explorer**: https://developers.facebook.com/tools/explorer/ and select your app at the top right.
3. Under **Permissions** add `pages_show_list`, `pages_read_engagement` and `pages_manage_posts`.
   Press **Generate Access Token** and approve it for your Page.
4. For a token that does not expire: https://developers.facebook.com/tools/debug/accesstoken/ → paste the token
   → **Debug** → **Extend Access Token** → copy the new token.
5. Back in the Graph API Explorer: put the new token in the "Access Token" field and run the query `me/accounts`.
   For your Page, copy the `id` (= **Page ID**) and the `access_token` (= **Page Access Token**).
6. Paste them into AI Social → **Save**.

While the app is in Development mode, it publishes normally to Pages that you manage.

### Instagram
Not supported yet: the Instagram API needs the image at a public URL, while AI Social runs on your computer.

---

## Everyday use

**Home:** the date, when your next post goes out, and **Your week**: the next 7 days with every scheduled post.
**+ Add** on a day opens a new post already set for that day. Until the basics are in place, **Start here** shows
what is left (an AI key, an account, a first post). After your first post you also get the key numbers, a chart of
posts per week (with a **Table** view), the split per platform, recent results and the state of your accounts.

**New post:**
1. **Where should it go out?** Tick the accounts.
2. **What should the AI write?** Write a topic (or pick one from your list, or press **Random**), choose the
   length, and add optional instructions (for example "mention the 20% off offer until Sunday").
   Press **Write with AI**: you get one text per platform, with a character counter.
3. **Text:** edit it freely, or press **Rewrite**.
4. **Image** (optional): **Upload image** or **AI image**.
5. **Publish:** **Now**, or **Later** with a date and time (or **In 1 hour**, **Tomorrow 09:00**, **Tomorrow 18:00**).

The **Preview** shows roughly how each post will look. Your draft is kept if you close the page by accident.

**Posts:** everything you scheduled or published, grouped by day, with filters (Scheduled, Published, Failed,
Cancelled). On a scheduled post you can **Edit** the text and time, **Publish now** or **Cancel post**. A failed
post can be sent again with **Try again**, once you have fixed the cause shown in its message.

### Scheduling: the app has to be running
Scheduled posts go out **only while AI Social is running** (window open, computer on and not asleep). If it was
closed when a post was due:
- up to **6 hours** late: the post goes out as soon as you start the app again,
- more than 6 hours late: it is marked **Failed** (so it does not go out at the wrong moment) and you can send it
  again from Posts.

On macOS, to keep the computer awake while the app runs: `caffeinate -i ./start.sh`.

### Language
**Settings → Language** switches the menus, buttons and messages between English and Greek, for the whole app.
The starter topics and writing style follow the switch as long as you have not edited them; your own text never
changes. The language **of your posts** is a separate setting: **Post language** under **Business and topics**.
When it is empty, the AI writes in the language of the topic.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| The start window says Python 3.10 or newer was not found («Δεν βρέθηκε Python 3.10 ή νεότερη») | Install Python from https://www.python.org/downloads/ and try again. On Windows tick "Add python.exe to PATH". |
| Installing the libraries failed | The first start needs internet. Try again. |
| Port 5050 is in use («Η θύρα 5050 χρησιμοποιείται») | Add `AISOCIAL_PORT=5051` to `.env`. If you use LinkedIn, change the redirect URL in the LinkedIn app to `http://localhost:5051/oauth/linkedin/callback` (and the Callback URI in the X app). |
| The browser did not open | Open http://localhost:5050. If the app is already running, the start script just opens the page. |
| X: 401 | Wrong keys. Copy them again (without spaces). |
| X: 403 | The app does not have "Read and write" (after changing it, create the Access Token again), there are no credits, or the same text was already posted. |
| X: 402 | The developer account has no credits or plan for posting. |
| LinkedIn: "redirect_uri does not match" | The redirect URL in the LinkedIn app must be **exactly** `http://localhost:5050/oauth/linkedin/callback`. |
| LinkedIn: 403 | The "Share on LinkedIn" product is missing. Add it, then press **Reconnect**. |
| LinkedIn: "The LinkedIn connection expired" | Press **Reconnect** (every 60 days). |
| Facebook: "The Page Access Token is invalid or expired" (190) | Get a new Page Access Token (steps 3-5 above). |
| "The saved details cannot be read" | `APP_SECRET` in `.env` changed. Restore the old `.env` (there is a `.env.bak` if you ran `init --new-key`) or enter the keys again in Settings. |
| A post failed with "…the post may have gone out" | The connection dropped while sending. Check the platform before you send it again, so it does not go out twice. |
| AI error (key, credits, limit) | Check the key and credits at Anthropic or OpenAI. **Check AI connection** in Settings → AI shows what is wrong. |

Details about every error are printed in the app's window (terminal).

---

## Security and data

- The app listens only locally (localhost: your computer). Other devices on your network cannot connect.
- API keys and tokens are stored **encrypted** (Fernet) in `instance/aisocial.db`, with the `APP_SECRET` from
  `.env` as the key. The app never shows them again (only the last 4 characters).
- Protection against other websites in the same browser (CSRF, DNS rebinding) and a strict Content-Security-Policy.
- **Do not share `.env` or the `instance/` folder.** Both are excluded from git.
- Access from another device (advanced): `AISOCIAL_HOST=0.0.0.0`, **always** with `AISOCIAL_PASSWORD=...`, and
  `AISOCIAL_PUBLIC_URL=` the address you will open. Ideally behind an HTTPS reverse proxy.

### Backup / moving to another computer
Copy the **`.env`** file and the **`instance/`** folder. Without the same `.env`, the saved keys cannot be read (you
would enter them again). `.venv` is not needed: it is rebuilt automatically.

---

## Advanced settings (`.env`)

Everything is optional except `APP_SECRET`, which is created automatically. Restart the app after a change.

| Variable | Default | What it does |
|---|---|---|
| `AISOCIAL_PORT` | `5050` | Port. |
| `AISOCIAL_HOST` | `127.0.0.1` | Address to listen on. Any other value requires `AISOCIAL_PASSWORD`. |
| `AISOCIAL_PUBLIC_URL` | `http://localhost:<port>` | The app's address (used for the LinkedIn redirect). |
| `AISOCIAL_PASSWORD` | – | Access password (Basic auth). |
| `AISOCIAL_ALLOWED_HOSTS` | – | Extra host names to accept, comma-separated (for example behind a reverse proxy). |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | – | Keys from here instead of the browser (these take priority). |
| `AI_TEXT_PROVIDER` | `auto` | `auto`, `anthropic` or `openai`. |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model. |
| `ANTHROPIC_EFFORT` | `low` | `low`, `medium`, `high`, `xhigh` or `max`. |
| `OPENAI_TEXT_MODEL` | `gpt-5-mini` | OpenAI model for text. |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | OpenAI model for images. |
| `LINKEDIN_API_VERSION` | automatic | LinkedIn API version (YYYYMM). Usually not needed. |
| `FACEBOOK_GRAPH_VERSION` | `v26.0` | Graph API version. |
| `AISOCIAL_DB_PATH` | `instance/aisocial.db` | Database file. |
| `AISOCIAL_MEDIA_DIR` | `instance/media` | Uploaded and generated images. |
| `AISOCIAL_SCHEDULER_INTERVAL` | `15` | How often (in seconds) scheduled posts are checked. |
| `AISOCIAL_MAX_LATE_MINUTES` | `360` | How late a post may go out before it is marked Failed. |

Commands (from the app's folder, with the Python in `.venv`):
- `python -m aisocial run --open`: start
- `python -m aisocial init`: create `.env` if it is missing
- `python -m aisocial init --new-key`: new `APP_SECRET` (keeps a backup in `.env.bak`; the keys must be entered again)

---

## For developers

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

The tests make no internet calls: the platforms and the AI SDKs are replaced with fakes.

```
aisocial/
  __init__.py        create_app(): puts the pieces together
  __main__.py        CLI: init / run (waitress server + scheduler)
  config.py          settings from .env
  crypto.py          encryption of keys and tokens
  db.py              SQLite: tables and queries
  i18n.py            interface language (English or Greek)
  scheduler.py       thread that publishes scheduled posts
  publisher.py       publishes one post and records the result
  security.py        host allow-list, CSRF, password, security headers
  guides.py          the connection guides shown in the app
  ai/                Claude and OpenAI providers, prompts
  platforms/         X, LinkedIn, Facebook
  web/               pages, JSON API, LinkedIn OAuth
  templates/, static/  UI (vanilla JS, no CDN)
start.py             one-click bootstrap (standard library only)
start.command / start.bat / start.sh
tests/
```

Every text the user sees is written in both languages where it is used: `L("Save", "Αποθήκευση")` in Python,
Jinja and JavaScript. A new platform is a subclass of `Platform` (`aisocial/platforms/base.py`) with `fields`,
`verify()` and `publish()`, registered in `build_platforms()`, with a guide in `guides.py`.

## Known limitations
- Instagram: not supported.
- LinkedIn: personal profile only; reconnect every 60 days.
- X: the API has a cost, charged by X.
- Scheduled posts need the app to be running.
- The calls to the platforms follow their documentation and are covered by tests, but the platforms change their
  rules often: make a **test post** on each account first.
- The messages in the start window and the command line are mostly in Greek.

## License
[MIT](LICENSE)
