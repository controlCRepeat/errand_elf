# ErrandElf 🧝

A conversational Telegram bot for managing your fridge. No commands needed — just talk to it naturally.

## How it works

Send a plain English message and the bot figures out what to do:

| What you type | What happens |
|---|---|
| `bought 2 oat milks expiring end of May` | Adds item |
| `used the eggs` | Decrements qty |
| `threw out the cheese` | Removes item |
| `what's in the fridge` | Lists all items |

Intent detection and natural language parsing is handled by Claude (Haiku). Data is stored in PostgreSQL via Supabase.

---

## Project structure

```
errand_elf/
├── bot.py          # Entry point — wires everything together
├── config.py       # Environment variables
├── database.py     # All DB logic (connect, read, write)
├── ai.py           # Claude API call and intent parsing
├── handlers.py     # One function per intent, Telegram replies
├── Procfile        # Tells Railway to run as a worker
├── runtime.txt     # Pins Python version
└── requirements.txt
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/errand_elf.git
cd errand_elf
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file locally:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://postgres.xxx:password@host:5432/postgres
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 4. Run locally

```bash
python bot.py
```

---

## Deploying to Railway

1. Push the repo to GitHub
2. In Railway: **New Project → Deploy from GitHub repo**
3. Add the following environment variables under **Variables**:
   - `TELEGRAM_BOT_TOKEN`
   - `DATABASE_URL` (Session pooler URL from Supabase — not the direct connection)
   - `ANTHROPIC_API_KEY`
4. Make sure the service type is **Worker** (not Web) — the Procfile handles this

---

## Database

Hosted on Supabase. Uses a single table:

```sql
CREATE TABLE fridge_current (
    item_name   TEXT PRIMARY KEY,
    expiry      DATE NOT NULL,
    qty         INT  NOT NULL,
    category    TEXT NOT NULL,  -- fresh | household | sauces
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

Table is created automatically on first run via `init_db()`.

---

## Environment variables

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `DATABASE_URL` | Supabase session pooler connection string (port 5432) |
| `ANTHROPIC_API_KEY` | From console.anthropic.com |