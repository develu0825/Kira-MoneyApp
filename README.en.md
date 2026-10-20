<div align="center">

<img src="app/icons/icon-512.png" width="110" alt="Kira" />

# Kira

**A budgeting app that shows what you *actually* spent — not just what left your account**

Pulls multiple accounts (KakaoBank, Toss) into one place, then strips out transfers between your own accounts, money you lent, and the part friends paid you back — leaving only *real spending*.

[Live demo](https://develu0825.github.io/Kira-MoneyApp/app/) · [한국어](README.md)

</div>

---

## Why I built it

Every budgeting app I tried had the same blind spots.

- **Transfers to my own other accounts** counted as "spending." I didn't spend it — I moved it.
- **Money I lent to friends** counted as spending too. It's coming back.
- **When I paid for the group and got reimbursed**, the full amount showed as my expense — even though I only paid 1/N.
- **Taxi pre-authorizations** got counted even though they're later canceled.

And the dealbreaker: **MyData-based auto budgeting apps (the Korean standard) don't allow minors to sign up.**
So I needed an app that pulls my KakaoBank/Toss transactions into one place and filters them by *my* rules to show only real spending. It didn't exist, so I built it.

> Kira isn't a budgeting app that *records everything* — it's one that *filters out* what isn't really spending.

---

## What makes it different

| | Typical app | **Kira** |
|---|---|---|
| Transfer between own accounts | Counted as spending | **Auto-detected → excluded** |
| Money lent out | Counted as spending | **Tracked separately as "owed to me"** |
| Group payment + reimbursement | Full amount | **Enter reimbursed amount → only my share** |
| Taxi pre-auth | Counted (double) | **Auto-excluded** |
| Categorization | Manual | **Auto by merchant keywords (81%)** |
| Budget targets | Set manually | **Auto from last month's actual spending** |
| Minors | Blocked by MyData | **Works (CSV / scraping based)** |
| Data storage | Company servers | **Your own device + encryption (AES-256)** |

The core is a single **"Real / All" toggle** — instantly compare filtered spending vs. everything that left your account.

---

## Screenshots

> Capture on your iPhone, drop into `docs/screenshots/`, and match the paths below.

<div align="center">

| Home · Real spending | Stats | Budget · Auto targets | Transaction detail |
|---|---|---|---|
| <img src="docs/screenshots/home.png" width="190"/> | <img src="docs/screenshots/stats.png" width="190"/> | <img src="docs/screenshots/budget.png" width="190"/> | <img src="docs/screenshots/detail.png" width="190"/> |

</div>

---

## Features

- **Real / All toggle** — filtered spending vs. total outflow
- **Auto-exclude** — self-transfers & taxi pre-auths detected automatically; tap to exclude/restore manually
- **Split-bill settlement** — enter the amount you got back → counts only your share
- **Auto-categorization** — merchant-keyword based (food, transit, shopping, culture, subscriptions, convenience, health)
- **Auto budget from last month** — last month's actual spending becomes this month's target; fixed once edited
- **Month picker · collapsible day groups · per-category detail · memos**
- **Lent money** — tracked separately as "owed to me"
- **PIN / Face ID lock · dark mode**
- **Installable PWA** — add to iPhone home screen like a native app (no App Store, free)

---

## How it works

```
[KakaoBank / Toss]
   │  ① CSV/Excel export   or   ② CODEF scraping
   ▼
[PC collector (Python)]  ── auto-categorize · detect self-transfer / pre-auth
   │  AES-256-GCM encryption
   ▼
[GitHub (public repo)]  ── data.enc (undecryptable without the passphrase)
   │
   ▼
[iPhone PWA]  ── decrypt with my passphrase → show · categorize · stats
```

- The repo is public, but transaction data is **encrypted** — unreadable without the passphrase.
- The phone app is **read-only**; keys, passphrase, and the source DB stay on the PC only.

---

## Tech stack

- **App**: vanilla HTML/CSS/JS single-file PWA (Service Worker · WebAuthn · Web Crypto)
- **Collector**: Python (easycodefpy, cryptography, openpyxl/msoffcrypto)
- **Crypto**: AES-256-GCM + PBKDF2 (Python ↔ browser Web Crypto interop)
- **Hosting**: GitHub Pages (free)

---

## Try it

1. Open the [live demo](https://develu0825.github.io/Kira-MoneyApp/app/) in iPhone **Safari**
2. Share → **Add to Home Screen**
3. (Connect real data) Export transactions from your bank app, then in `collector/`:
   ```bash
   pip install -r collector/requirements.txt
   python import_csv.py transactions.xlsx --bank 카카오뱅크
   python publish.py
   ```

See `docs/codef-setup-checklist.md` for detailed setup.

---

## Security

- CODEF keys, passphrase, `ConnectedId`, source `money.db`, and `.env` are **never committed** (`.gitignore`)
- Transaction data is uploaded only after AES-256-GCM encryption
- The passphrase (`KIRA_PASSPHRASE`) exists only on the PC and the phone

---

## Status & roadmap

- [x] Installable PWA · encrypted pipeline · PIN/Face ID
- [x] Auto-categorization · self-transfer/pre-auth exclusion · settlement · auto budget
- [x] CSV/Excel import (incl. password-protected)
- [ ] Quick manual entry
- [ ] Settings backup/restore
- [ ] Monthly trend chart

---

## Author / Contact

Started it just for myself, but anyone with a **similar problem** — or who wants to **help improve it** — is welcome.

- GitHub: [@develu0825](https://github.com/develu0825)
- Email: **develu0825@gmail.com**
- Ideas · bugs · interest → open an [Issue](https://github.com/develu0825/Kira-MoneyApp/issues)

> A budgeting app a minor developer built because *I needed it*. Feedback means a lot 🙌

---

<div align="center">
<sub>Made with 💜 · Kira</sub>
</div>
