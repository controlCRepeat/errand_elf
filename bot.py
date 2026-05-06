import os
import time
import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    for attempt in range(5):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.commit()
            print("DB connection successful ✅")
            return
        except Exception as e:
            wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
            print(f"DB connection failed (attempt {attempt+1}): {e}")
            print(f"Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Could not connect to DB after 5 attempts")

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hello! I'm alive 👋")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text(f"You said: {u.message.text}")))
    print("Bot is running...")
    app.run_polling()