# AI Email Reading Agent

Monitors a Gmail inbox every 2 minutes, classifies emails by importance using keyword rules, and surfaces only the ones that actually need attention on a live dashboard. Newsletters, receipts, and promos are silently filtered out.

---

## Getting started

You need Docker. That's it.

```bash
cp .env.example .env
docker compose up --build
```

Open **http://localhost:8000** — the dashboard loads pre-populated with sample emails so you can see it working right away.

---

## Connecting a real Gmail inbox

Google won't let you log in via IMAP with your regular password. You'll need an **App Password**.

**Step 1 — Enable 2-Step Verification** (skip if you already have it on)  
Go to [myaccount.google.com/security](https://myaccount.google.com/security) and turn it on.

**Step 2 — Create an App Password**  
Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), create one (name it anything), and copy the 16-character code it shows you.

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

## How it classifies emails

Every incoming email is checked against keyword rules in a fixed priority order — the first match wins. Receipts are always checked first so a "payment successful" email never accidentally fires the payment failure rule.

| Category | Priority | Shown on dashboard | Example triggers |
|---|---|---|---|
| PAYMENT_ISSUE | HIGH | Yes | failed charge, refund, expired card, overdue invoice, chargeback |
| SERVER_DOWN | HIGH | Yes | outage, 503, deploy failed, health check alert, DB connection error |
| CLIENT_COMPLAINT | HIGH | Yes | cancel my account, legal action, BBB, threatening to leave, want a refund |
| SECURITY_ALERT | HIGH | Yes | suspicious login, data breach, CVE, phishing, credentials exposed |
| URGENT_REQUEST | MEDIUM | Yes | urgent, ASAP, action required, pending approval, deadline, blocker |
| GENERAL | MEDIUM | Yes | anything that looks like a real person wrote it |
| SPAM | LOW | No | sale, discount, you're a winner, crypto, casino |
| SUBSCRIPTION | LOW | No | newsletter, digest, liked your post, app update, maintenance notice |

---

## Dashboard

Auto-refreshes every 15 seconds. Use **Poll now** to fetch immediately.

Each card shows the sender, subject, priority (colour-coded), category, the reason it was flagged, and when it arrived. Filter by priority or classification method using the tabs at the top.

---

## Project layout

```
email-agent/
├── docker-compose.yml
├── Dockerfile
├── .env.example           ← copy this to .env and fill in your details
├── mock_data/emails.json  ← sample emails used in mock mode
└── backend/
    ├── requirements.txt
    ├── static/index.html  ← dashboard UI
    └── app/
        ├── main.py        ← FastAPI app + background scheduler
        ├── poller.py      ← fetch → deduplicate → classify → store
        ├── classifier.py  ← all the keyword rules live here
        ├── sources.py     ← mock and Gmail IMAP sources
        ├── storage.py     ← SQLite, handles deduplication
        └── models.py      ← shared data types
```

---

## API endpoints

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

## A few things to keep in mind

- The `.env` file contains your real credentials — it's git-ignored for a reason. Only `.env.example` gets committed.
- Use an App Password for Gmail, never your actual account password.
- The dashboard has no login — keep it running locally.
- Each email is processed exactly once. Processed IDs are stored in SQLite and survive container restarts via a Docker volume.
