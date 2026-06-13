# AI Email Reading Agent

A lightweight agent that monitors an email inbox (or mock dataset), classifies incoming emails by importance, and surfaces only the ones that actually need attention on a live dashboard. Newsletters, receipts, and promos are silently filtered out — the idea being you open the dashboard and immediately see what matters.

Built with FastAPI, SQLite, and a rule-based classifier. Polling runs in the background every 2 minutes.

---

## Quick start

You need Docker. That's it.

```bash
cp .env.example .env
docker compose up --build
```

Open **http://localhost:8000** — the dashboard loads pre-populated with sample emails so you can see it working right away without connecting a real inbox.

---

## Connecting a real Gmail inbox

Google won't let you log in via IMAP with your regular password, so you'll need an **App Password**.

**Step 1 — Enable 2-Step Verification** (skip if it's already on)  
Go to [myaccount.google.com/security](https://myaccount.google.com/security).

**Step 2 — Create an App Password**  
Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), create one (call it anything), and copy the 16-character code it gives you.

**Step 3 — Edit `.env`**

```env
EMAIL_SOURCE=gmail
IMAP_USER=you@gmail.com
IMAP_PASSWORD=abcd efgh ijkl mnop
```

**Step 4 — Rebuild**

```bash
docker compose up --build
```

---

## How classification works

The task asked for AI or rules to classify emails. I went with a **rule-based classifier** — the decision was partly practical (no API cost, no rate limits, works offline) and partly because it's actually the right tool for this specific problem. Email classification based on intent doesn't need a language model when you can express the same logic as patterns: "card declined", "payment failed", "outage", "I want a refund" are all unambiguous signals.

Every email gets checked against keyword/regex patterns in a fixed priority order. The first match wins. Receipts are always checked first — otherwise a "payment successful" email would accidentally fire the payment failure rule because both contain the word "payment".

| Category | Priority | Shown on dashboard | What triggers it |
|---|---|---|---|
| PAYMENT_ISSUE | HIGH | Yes | failed charge, card declined, refund, overdue invoice, chargeback |
| SERVER_DOWN | HIGH | Yes | outage, 503, deploy failed, health check alert, DB connection error |
| CLIENT_COMPLAINT | HIGH | Yes | cancel my account, legal action, BBB, threatening to leave, want a refund |
| SECURITY_ALERT | HIGH | Yes | suspicious login, data breach, CVE, phishing, credentials exposed |
| URGENT_REQUEST | MEDIUM | Yes | urgent, ASAP, action required, pending approval, deadline, blocker |
| GENERAL | MEDIUM | Yes | anything that doesn't match a noise pattern — probably a real person |
| SPAM | LOW | No | sale, discount, you're a winner, crypto, casino |
| SUBSCRIPTION | LOW | No | newsletter, digest, liked your post, app update, maintenance notice |

The classifier lives entirely in [`backend/app/classifier.py`](backend/app/classifier.py) — all the patterns are there and easy to extend.

---

## Dashboard

Auto-refreshes every 15 seconds. Hit **Poll now** to fetch immediately without waiting.

Each card shows: sender, subject, priority (colour-coded), category, the reason it was flagged, and when it arrived. You can filter by priority or classification method using the tabs at the top.

Stats at the top of the page show total emails processed, how many were flagged as important, and how many were filtered out.

---

## Project layout

```
AI-Email-Reader/
├── docker-compose.yml
├── Dockerfile
├── .env.example           ← copy this to .env and fill in your details
├── mock_data/emails.json  ← sample emails covering every category
└── backend/
    ├── requirements.txt
    ├── static/index.html  ← dashboard (single HTML file, no build step)
    └── app/
        ├── main.py        ← FastAPI app + background scheduler
        ├── poller.py      ← fetch → deduplicate → classify → store
        ├── classifier.py  ← all keyword/regex rules live here
        ├── sources.py     ← mock and Gmail IMAP sources
        ├── storage.py     ← SQLite, handles deduplication
        └── models.py      ← shared Pydantic models
```

---

## Tech stack

- **FastAPI** — API and static file serving
- **APScheduler** — background polling every N seconds
- **SQLite** — stores processed email IDs and notifications, survives container restarts
- **IMAP** — connects to Gmail (or any IMAP server) via Python's standard library
- **Vanilla HTML/CSS/JS** — no frontend framework, no build step

---

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/` | The dashboard |
| GET | `/api/notifications` | JSON — important emails + stats |
| POST | `/api/poll` | Trigger an immediate inbox poll |
| GET | `/api/health` | Health check |

---

## Running without Docker

```bash
cd backend
pip install -r requirements.txt
EMAIL_SOURCE=mock MOCK_DATA_PATH=../mock_data/emails.json uvicorn app.main:app --reload
```

---

## Limitations

**No LLM / AI model used** — I originally planned to run emails through Claude or GPT-4 for classification, but both require a paid API subscription. Given the cost constraint, I built a rule-based classifier instead. It handles the common cases well, but it has real blind spots:

- **Context-free** — it matches keywords, not meaning. An email saying "our server is not down anymore" would still fire the SERVER_DOWN rule because of the word "down".
- **English only** — patterns are written in English and won't work for emails in other languages.
- **Misses subtlety** — a politely worded complaint with no strong keywords ("I've been having some trouble with my account...") gets classified as GENERAL, not CLIENT_COMPLAINT.
- **No learning** — the rules don't adapt. If a new pattern of spam or alerts emerges, the patterns have to be manually updated.
- **Gmail only (for live mode)** — the IMAP source is wired for Gmail. Other providers would need minor config changes (host, port).
- **No authentication on the dashboard** — it's meant to run locally or in a private network. Don't expose it publicly without putting something in front of it.
- **Poll-based, not push** — the agent polls on a fixed interval rather than receiving webhooks, so there's always a small delay between an email arriving and it appearing on the dashboard.

An LLM-based classifier would fix most of the first three — it understands context and nuance that regex simply can't. That's the natural next step if API access becomes available.

---

## Notes on credentials

- The `.env` file is git-ignored — never commit it. Only `.env.example` goes to GitHub.
- Use an App Password for Gmail, not your actual account password.
- Each email is processed exactly once. Processed IDs are stored in SQLite and survive container restarts via a Docker volume.
