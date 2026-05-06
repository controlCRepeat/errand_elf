from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ai import parse_intent
from database import get_all_items, get_item, upsert_item, delete_item
from config import EXPIRY_WARNING_DAYS

HELP_TEXT = (
    "I didn't quite get that. Try:\n"
    "• <i>bought 2 oat milks expiring end of May</i>\n"
    "• <i>used the eggs</i>\n"
    "• <i>threw out the cheese</i>\n"
    "• <i>what's in the fridge</i>"
)


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

async def handle_add(update: Update, parsed: dict):
    item_name = parsed["item_name"]
    qty       = int(parsed.get("qty", 1))
    category  = parsed.get("category", "fresh").capitalize()
    expiry    = datetime.strptime(parsed["expiry"], "%Y-%m-%d").date()

    existing = get_item(item_name)
    action   = "updated" if existing else "added"
    upsert_item(item_name, expiry, qty, category)

    days_left = (expiry - datetime.now().date()).days
    await update.message.reply_text(
        f"✅ <b>{item_name}</b> {action}\n"
        f"Category: {category} | Qty: {qty} | Expiry: {expiry.strftime('%d %b %y')} ({days_left}d left)",
        parse_mode="HTML"
    )


async def handle_consume(update: Update, parsed: dict):
    item_name      = parsed["item_name"]
    qty_to_consume = int(parsed.get("qty", 1))
    row            = get_item(item_name)

    if not row:
        await update.message.reply_text(
            f"I don't see <b>{item_name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    new_qty = row["qty"] - qty_to_consume
    if new_qty <= 0:
        delete_item(item_name)
        await update.message.reply_text(
            f"✅ <b>{item_name}</b> fully consumed and removed.", parse_mode="HTML"
        )
    else:
        upsert_item(item_name, row["expiry"], new_qty, row["category"])
        await update.message.reply_text(
            f"✅ Consumed {qty_to_consume} <b>{item_name}</b>. {new_qty} remaining.",
            parse_mode="HTML"
        )


async def handle_throw(update: Update, parsed: dict):
    item_name = parsed["item_name"]

    if not get_item(item_name):
        await update.message.reply_text(
            f"I don't see <b>{item_name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    delete_item(item_name)
    await update.message.reply_text(f"🗑 <b>{item_name}</b> thrown away.", parse_mode="HTML")


async def handle_view(update: Update, fridge: list):
    if not fridge:
        await update.message.reply_text("The fridge is empty.")
        return

    today         = datetime.now().date()
    expiring_soon = []
    not_urgent    = []

    for row in fridge:
        days_left = (row["expiry"] - today).days
        line      = f"{row['item_name']} x{row['qty']} — {days_left}d left"
        (expiring_soon if days_left < EXPIRY_WARNING_DAYS else not_urgent).append(line)

    parts = []
    if expiring_soon:
        parts.append("<b>☢️ Expiring soon</b>\n" + "\n".join(expiring_soon))
    if not_urgent:
        parts.append("<b>🐝 Not urgent</b>\n" + "\n".join(not_urgent))

    await update.message.reply_text("\n\n".join(parts), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Main entry point for all messages
# ---------------------------------------------------------------------------

INTENT_HANDLERS = {
    "add":     handle_add,
    "consume": handle_consume,
    "throw":   handle_throw,
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text   = update.message.text
    fridge = get_all_items()

    try:
        actions = parse_intent(text, fridge)

        for parsed in actions:
            intent = parsed.get("intent")

            if intent == "view":
                await handle_view(update, fridge)
            elif intent in INTENT_HANDLERS:
                await INTENT_HANDLERS[intent](update, parsed)
            else:
                await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

    except Exception as e:
        print(f"Error handling message: {e}")
        await update.message.reply_text("Something went wrong, please try again.")
