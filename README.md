# Kira — personal money app

Kira is a personal spending tracker for a single user. Unlike a normal budgeting
app that logs *everything*, Kira's job is to show **what I actually spent** — after
automatically setting aside transfers to my own accounts and money I lent to
friends, which aren't really spending.

## Why

Most budgeting apps count a transfer to my own savings, or ₩150,000 I lent a
friend, as "spending." Kira filters those out so the headline number is my *real*
consumption.

## How it works

```
[CODEF API] ←(my bank auth)— KakaoBank / Toss / Shinhan
     │  transactions
     ▼
[collector]  (Python, runs on my PC ~1×/day)
     │  → SQLite
     ▼
[Kira app]   shows only real spending; lets me exclude / categorize
```

- **CODEF** scrapes each bank on my behalf, so I don't integrate every bank myself.
- The **collector** pulls transactions and stores them locally.
- The **app** reads that data and lets me mark things as "not spending"
  (self-transfer, loan, refund…). Exclusions are saved, so they survive the next sync.

## Repo contents

| Path | What |
|------|------|
| `docs/money-app-mockup.html` | Kira UI prototype — interactive, self-contained HTML (sample data) |
| `collector/codef_collector.py` | Daily CODEF → SQLite collector |
| `collector/requirements.txt` | Collector dependencies |
| `docs/codef-setup-checklist.md` | CODEF signup / free-tier / auth checklist |

## App features (prototype)

- **Kira / All toggle** — real spending vs. total outflow
- **Exclude from spending** — tap to drop self-transfers, loans, refunds; self-transfers auto-detected
- **Category budgets** — per-category targets (food, date, shopping…); *Date* is a cross-cutting tag that can overlap other categories
- **Income & Left** — this month's income minus real spending
- **Lent** — money lent out, tracked as "owed" instead of spending
- **Stats** — spending by category
- **Accounts / Settings** — CODEF sync status, auto-exclude rules, dark mode

## Status

Prototype UI + collector scaffold. Not yet wired to live CODEF data.

## Run the prototype

Open `docs/money-app-mockup.html` in any browser — everything is inlined, no build step.

## Collector setup

See `docs/codef-setup-checklist.md`. In short:

```bash
pip install -r collector/requirements.txt
export CODEF_CLIENT_ID=...
export CODEF_CLIENT_SECRET=...
export CODEF_PUBLIC_KEY=...
python collector/codef_collector.py
```

## Security

- **Never commit** CODEF keys, RSA keys, `ConnectedId`, bank credentials, or `money.db`.
- Keys live in environment variables only (see `.gitignore`).

## Roadmap

- [ ] Wire collector to live CODEF (free demo tier)
- [ ] Ship the UI to iPhone as a PWA (Add to Home Screen) + free backend
- [ ] (later) SwiftUI native app
