from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_BOT_TOKEN
from database import init_db
from handlers import handle_message, cmd_intro, cmd_fridge, cmd_expiring, cmd_restock


def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands — no AI credits used
    app.add_handler(CommandHandler("intro",     cmd_intro))
    app.add_handler(CommandHandler("fridge",    cmd_fridge))
    app.add_handler(CommandHandler("expiring",  cmd_expiring))
    app.add_handler(CommandHandler("restock",   cmd_restock))

    # Free text — goes through Gemini
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("ErrandElf is running...")
    app.run_polling()


if __name__ == "__main__":
    main()