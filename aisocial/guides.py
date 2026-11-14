"""Step-by-step setup guides shown in the app next to each form, in the interface language."""

from __future__ import annotations

from .i18n import L


def ai_guides() -> dict:
    return {
        "anthropic": {
            "title": L("Claude (Anthropic), recommended for writing", "Claude (Anthropic), προτείνεται για το κείμενο"),
            "summary": L(
                "Writes the posts. You pay only for what you use (usually a few cents per post).",
                "Γράφει τα posts. Πληρώνεις μόνο όσο το χρησιμοποιείς (συνήθως λίγα cents ανά post).",
            ),
            "steps": [
                L(
                    "Open https://platform.claude.com and create an account or log in.",
                    "Άνοιξε το https://platform.claude.com και φτιάξε λογαριασμό ή κάνε login.",
                ),
                L(
                    "Go to Settings → Billing and add a few credits (for example $5).",
                    "Πήγαινε Settings → Billing και πρόσθεσε λίγα credits (π.χ. 5$).",
                ),
                L(
                    "Go to Settings → API keys → “Create key” and give it a name (for example “AI Social”).",
                    "Πήγαινε Settings → API keys → «Create key» και δώσε ένα όνομα (π.χ. «AI Social»).",
                ),
                L(
                    "Copy the key (it starts with sk-ant-) and paste it here. You can see it only once.",
                    "Αντέγραψε το key (ξεκινά με sk-ant-) και επικόλλησέ το εδώ. Το βλέπεις μόνο μία φορά.",
                ),
            ],
            "notes": [],
        },
        "openai": {
            "title": L(
                "OpenAI: for AI images (and as an alternative for writing)",
                "OpenAI: για εικόνες με AI (και εναλλακτικά για κείμενο)",
            ),
            "summary": L(
                "Needed only if you want the AI to make images too, or if you prefer OpenAI "
                "for writing. Without it you can always upload your own images.",
                "Χρειάζεται μόνο αν θέλεις το AI να φτιάχνει και εικόνες, ή αν προτιμάς το OpenAI "
                "για το κείμενο. Χωρίς αυτό μπορείς πάντα να ανεβάζεις δικές σου εικόνες.",
            ),
            "steps": [
                L("Open https://platform.openai.com and log in.", "Άνοιξε το https://platform.openai.com και κάνε login."),
                L("Go to Settings → Billing and add credits.", "Πήγαινε Settings → Billing και πρόσθεσε credits."),
                L(
                    "For images: Settings → Organization → General → “Verify Organization”. OpenAI requires it for the image models.",
                    "Για εικόνες: Settings → Organization → General → «Verify Organization». Το OpenAI το ζητά για τα μοντέλα εικόνας.",
                ),
                L(
                    "Open https://platform.openai.com/api-keys and press “Create new secret key”.",
                    "Άνοιξε το https://platform.openai.com/api-keys και πάτα «Create new secret key».",
                ),
                L(
                    "Copy the key (it starts with sk-) and paste it here.",
                    "Αντέγραψε το key (ξεκινά με sk-) και επικόλλησέ το εδώ.",
                ),
            ],
            "notes": [],
        },
    }


def platform_guides(settings) -> dict:
    base = settings.public_url
    redirect = settings.linkedin_redirect_uri
    return {
        "x": {
            "title": L("Connect X (Twitter)", "Σύνδεση X (Twitter)"),
            "summary": L(
                "You create a developer app on X and copy 4 keys. It takes about 10 minutes.",
                "Φτιάχνεις ένα developer app στο X και αντιγράφεις 4 keys. Θέλει περίπου 10 λεπτά.",
            ),
            "steps": [
                L(
                    "Open https://developer.x.com and log in with the X account that will post. "
                    "If asked, create a developer account and briefly describe your use "
                    "(for example “Publishing my business's posts”).",
                    "Άνοιξε το https://developer.x.com και κάνε login με τον λογαριασμό X που θα κάνει τα posts. "
                    "Αν σου ζητηθεί, φτιάξε developer account και γράψε σύντομα τη χρήση "
                    "(π.χ. «Δημοσίευση posts της επιχείρησής μου»).",
                ),
                L(
                    "In the Developer Portal, open your App (or create a new App inside a Project).",
                    "Στο Developer Portal άνοιξε το App σου (ή δημιούργησε νέο App μέσα σε ένα Project).",
                ),
                L(
                    "In the App → “User authentication settings” → “Set up”: App permissions = “Read and write”, "
                    f"Type of App = “Web App, Automated App or Bot”, Callback URI = {base}, "
                    "Website URL = your website (or https://example.com). Save.",
                    "Στο App → «User authentication settings» → «Set up»: App permissions = «Read and write», "
                    f"Type of App = «Web App, Automated App or Bot», Callback URI = {base}, "
                    "Website URL = η σελίδα σου (ή https://example.com). Αποθήκευση.",
                ),
                L(
                    "In the App → “Keys and tokens” → “API Key and Secret” → “Regenerate”. "
                    "Copy the API Key and the API Key Secret.",
                    "Στο App → «Keys and tokens» → «API Key and Secret» → «Regenerate». "
                    "Αντέγραψε το API Key και το API Key Secret.",
                ),
                L(
                    "In the same place → “Access Token and Secret” → “Generate”. It must say "
                    "“Read and Write”. If it says only “Read”, press “Regenerate” (it was made before step 3).",
                    "Στο ίδιο σημείο → «Access Token and Secret» → «Generate». Πρέπει να γράφει "
                    "«Read and Write». Αν γράφει μόνο «Read», πάτα «Regenerate» (φτιάχτηκε πριν το βήμα 3).",
                ),
                L(
                    "Paste the 4 keys here, press “Save” and then “Check”.",
                    "Επικόλλησε τα 4 keys εδώ, πάτα «Αποθήκευση» και μετά «Έλεγχος».",
                ),
            ],
            "notes": [
                L(
                    "X charges for API use. If a post fails with a credits error (402/403), "
                    "add credits or choose a plan in the developer portal.",
                    "Το X χρεώνει τη χρήση του API. Αν το post βγάλει σφάλμα για credits (402/403), "
                    "πρόσθεσε credits ή διάλεξε πλάνο στο developer portal.",
                ),
            ],
            "copy": None,
        },
        "linkedin": {
            "title": L("Connect LinkedIn (personal profile)", "Σύνδεση LinkedIn (προσωπικό προφίλ)"),
            "summary": L(
                "You create a free LinkedIn app, add 2 products and press “Connect”. About 10 minutes.",
                "Φτιάχνεις ένα δωρεάν LinkedIn app, προσθέτεις 2 products και πατάς «Σύνδεση». Περίπου 10 λεπτά.",
            ),
            "steps": [
                L(
                    "Open https://www.linkedin.com/developers/apps and press “Create app”.",
                    "Άνοιξε το https://www.linkedin.com/developers/apps και πάτα «Create app».",
                ),
                L(
                    "Fill in the App name, LinkedIn Page and logo, and accept the terms. LinkedIn asks for "
                    "a Company Page: if you don't have one, make a simple one with “Create a LinkedIn Page”.",
                    "Συμπλήρωσε App name, LinkedIn Page, logo και αποδέξου τους όρους. Το LinkedIn ζητά "
                    "μια Company Page: αν δεν έχεις, φτιάξε μια απλή από το «Create a LinkedIn Page».",
                ),
                L(
                    "“Products” tab: add “Share on LinkedIn” and “Sign In with LinkedIn using "
                    "OpenID Connect”. They are approved right away.",
                    "Καρτέλα «Products»: πρόσθεσε «Share on LinkedIn» και «Sign In with LinkedIn using "
                    "OpenID Connect». Εγκρίνονται αμέσως.",
                ),
                L(
                    f"“Auth” tab → “Authorized redirect URLs for your app” → “Add redirect URL” and enter exactly: {redirect}",
                    f"Καρτέλα «Auth» → «Authorized redirect URLs for your app» → «Add redirect URL» και βάλε ακριβώς: {redirect}",
                ),
                L(
                    "On the same tab, copy the Client ID and the Primary Client Secret, paste them "
                    "here and press “Save”.",
                    "Στην ίδια καρτέλα αντέγραψε το Client ID και το Primary Client Secret, επικόλλησέ τα "
                    "εδώ και πάτα «Αποθήκευση».",
                ),
                L(
                    "Press “Connect LinkedIn”, log in and approve. You will come back here automatically.",
                    "Πάτα «Σύνδεση LinkedIn», κάνε login και έγκρινε. Θα επιστρέψεις αυτόματα εδώ.",
                ),
            ],
            "notes": [
                L(
                    "The connection lasts 60 days. Then you press “Reconnect” (the app reminds you).",
                    "Η σύνδεση ισχύει 60 μέρες. Μετά πατάς «Επανασύνδεση» (το app σού το θυμίζει).",
                ),
                L(
                    "Posts go to your personal profile. For a Company Page, LinkedIn requires special "
                    "approval (Community Management API).",
                    "Τα posts γίνονται στο προσωπικό σου προφίλ. Για Company Page το LinkedIn ζητά ειδική "
                    "έγκριση (Community Management API).",
                ),
            ],
            "copy": redirect,
        },
        "facebook": {
            "title": L("Connect a Facebook Page", "Σύνδεση Facebook Page"),
            "summary": L(
                "You need a Facebook Page (not a personal profile), a developer app and a "
                "Page Access Token. About 15 minutes.",
                "Χρειάζεσαι μια Facebook Σελίδα (όχι προσωπικό προφίλ), ένα developer app και ένα "
                "Page Access Token. Περίπου 15 λεπτά.",
            ),
            "steps": [
                L(
                    "Open https://developers.facebook.com/apps and press “Create App”. Choose the use case "
                    "for managing a Page (for example “Manage everything on your Page”) or “Other” → “Business”.",
                    "Άνοιξε το https://developers.facebook.com/apps και πάτα «Create App». Διάλεξε τη χρήση "
                    "για διαχείριση Σελίδας (π.χ. «Manage everything on your Page») ή «Other» → «Business».",
                ),
                L(
                    "Open the Graph API Explorer: https://developers.facebook.com/tools/explorer/ and "
                    "choose your app at the top right.",
                    "Άνοιξε το Graph API Explorer: https://developers.facebook.com/tools/explorer/ και "
                    "διάλεξε το app σου πάνω δεξιά.",
                ),
                L(
                    "Under “Permissions” add: pages_show_list, pages_read_engagement, pages_manage_posts. "
                    "Press “Generate Access Token” and approve it for your Page.",
                    "Στο «Permissions» πρόσθεσε: pages_show_list, pages_read_engagement, pages_manage_posts. "
                    "Πάτα «Generate Access Token» και έγκρινε για τη Σελίδα σου.",
                ),
                L(
                    "For a token that does not expire: open https://developers.facebook.com/tools/debug/accesstoken/ , "
                    "paste the token, press “Debug” and then “Extend Access Token”. Copy the new token.",
                    "Για token που δεν λήγει: άνοιξε το https://developers.facebook.com/tools/debug/accesstoken/ , "
                    "επικόλλησε το token, πάτα «Debug» και μετά «Extend Access Token». Αντέγραψε το νέο token.",
                ),
                L(
                    "Go back to the Graph API Explorer, put the new token in the “Access Token” field and run the "
                    "query me/accounts . In the result, under your Page, copy the “id” (this is the "
                    "Page ID) and the “access_token” (this is the Page Access Token).",
                    "Γύρνα στο Graph API Explorer, βάλε το νέο token στο πεδίο «Access Token» και τρέξε το "
                    "query me/accounts . Στο αποτέλεσμα, στη Σελίδα σου, αντέγραψε το «id» (αυτό είναι το "
                    "Page ID) και το «access_token» (αυτό είναι το Page Access Token).",
                ),
                L(
                    "Paste the Page ID and Page Access Token here, press “Save” and then “Check”.",
                    "Επικόλλησε Page ID και Page Access Token εδώ, πάτα «Αποθήκευση» και μετά «Έλεγχος».",
                ),
            ],
            "notes": [
                L(
                    "While the app is in Development mode, it posts normally to Pages that you manage.",
                    "Όσο το app είναι σε Development mode, δημοσιεύει κανονικά σε Σελίδες που διαχειρίζεσαι εσύ.",
                ),
                L(
                    "Instagram is not supported yet: its API needs the image uploaded to a public URL.",
                    "Το Instagram δεν υποστηρίζεται ακόμα: το API του θέλει την εικόνα ανεβασμένη σε δημόσιο URL.",
                ),
            ],
            "copy": None,
        },
    }
