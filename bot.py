import logging
import io
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from dotenv import load_dotenv
load_dotenv()

# Render requires a port to be open — run a minimal health server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Warehouse bot is running")
    def log_message(self, *args):
        pass  # silence access logs

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.getLogger(__name__).info(f"Health server on port {port}")

from config import TELEGRAM_TOKEN
from groq_parser import parse_message
from sheets import get_stock, add_stock, deduct_stock, add_new_product, update_rate
from pdf_generator import generate_delivery_receipt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ── /start ───────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏭 *Warehouse Bot Ready!*\n\n"
        "Yeh cheezein bhej sakte ho:\n\n"
        "📦 *Stock check karo:*\n`kitna hai Waaree 575 DCR`\n\n"
        "➕ *Maal aaya:*\n`aaya 100 Waaree 575 DCR`\n\n"
        "🚛 *Truck loading:*\n`truck HR55AB1234: Waaree 575 DCR x20, Polycab 5kw 3P x5`\n\n"
        "🆕 *Naya product add karo:*\n`naya product: Solar Panel, Waaree, 650W, DCR`",
        parse_mode="Markdown"
    )


# ── Main message handler ─────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    sender    = update.message.from_user.first_name or "Unknown"
    chat_id   = update.message.chat_id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    parsed = parse_message(user_text, sender)
    intent = parsed.get("intent", "unknown")
    logger.info(f"User={sender} | Intent={intent} | Text={user_text[:60]}")

    if intent == "check_stock":
        await _handle_check_stock(update, parsed)

    elif intent == "add_stock":
        await _handle_add_stock(update, parsed, sender)

    elif intent == "ship_out":
        await _handle_ship_out(update, context, parsed, sender, chat_id)

    elif intent == "add_product":
        await _handle_add_product(update, parsed, sender)

    elif intent == "update_rate":
        await _handle_update_rate(update, parsed)

    else:
        await update.message.reply_text(
            "🙏 Samajh nahi aaya bhai.\n\n"
            "Aise bhejo:\n"
            "• `kitna hai Waaree 575 DCR`\n"
            "• `aaya 50 Adani 540 DCR`\n"
            "• `truck HR55AB1234: Waaree 575 x10`\n\n"
            "• `/start` — poora guide dekho",
            parse_mode="Markdown"
        )


# ── Check stock ──────────────────────────────────────────────────
async def _handle_check_stock(update, parsed):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text("Kaunsa product? Dobara bhejo.")
        return

    lines = []
    for item in items:
        info = get_stock(item["brand"], item["spec"], item.get("type", "DCR"))
        if not info["found"]:
            lines.append(f"❌ *{item['brand']} {item['spec']} {item.get('type','')}* — sheet mein nahi mila")
            continue
        qty  = info["quantity"]
        rate = info["rate"]
        if qty == 0:
            status = "❌ Out of Stock"
        elif qty < 5:
            status = "⚠️ Low Stock"
        else:
            status = "✅ In Stock"
        rate_str = f"₹{rate}" if rate and str(rate).strip() not in ("0", "", "N/A") else "Rate set nahi"
        lines.append(
            f"*{info['brand']} {info['spec']} {info['type']}*\n"
            f"Stock: *{qty} units* {status}\n"
            f"Rate: {rate_str}"
        )
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


# ── Add stock ────────────────────────────────────────────────────
async def _handle_add_stock(update, parsed, sender):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text("Kitna add karna hai? Dobara bhejo.")
        return

    lines = []
    for item in items:
        qty = item.get("quantity", 0)
        if not qty or int(qty) <= 0:
            lines.append(f"❌ Quantity missing: {item['brand']} {item['spec']}")
            continue
        result = add_stock(
            item["brand"], item["spec"], item.get("type", "DCR"),
            int(qty), sender
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*\n"
                f"{result['before']} → *{result['after']}* (+{result['quantity']})"
            )
        else:
            lines.append(f"❌ {result['error']}")

    await update.message.reply_text(
        "📦 *Stock Updated:*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown"
    )


# ── Ship out ─────────────────────────────────────────────────────
async def _handle_ship_out(update, context, parsed, sender, chat_id):
    items      = parsed.get("items", [])
    vehicle_no = parsed.get("vehicle_no") or "NOT PROVIDED"

    if not items:
        await update.message.reply_text("Kaunsa maal ja raha hai? Dobara bhejo.")
        return

    await update.message.reply_text(
        f"🚛 Processing shipment for vehicle *{vehicle_no}*...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")

    results = []
    errors  = []

    for item in items:
        qty = item.get("quantity", 0)
        if not qty or int(qty) <= 0:
            errors.append(f"Quantity missing for {item['brand']} {item['spec']}")
            continue
        result = deduct_stock(
            item["brand"], item["spec"], item.get("type", "DCR"),
            int(qty), vehicle_no, sender
        )
        if result["success"]:
            results.append(result)
        else:
            errors.append(result.get("error", "Unknown error"))

    if not results and errors:
        await update.message.reply_text(
            "❌ *Shipment fail ho gaya:*\n\n" + "\n".join(errors),
            parse_mode="Markdown"
        )
        return

    # Generate PDF
    pdf_items = [
        {
            "brand":    r["brand"],
            "spec":     r["spec"],
            "type":     r["type"],
            "quantity": r["quantity"],
            "rate":     r.get("rate", 0)
        }
        for r in results
    ]

    pdf_bytes = generate_delivery_receipt(vehicle_no, sender, pdf_items)
    pdf_io    = io.BytesIO(pdf_bytes)
    pdf_name  = f"receipt_{vehicle_no}_{datetime.now().strftime('%d%b%Y')}.pdf"

    total_qty = sum(r["quantity"] for r in results)
    try:
        total_val = sum(
            r["quantity"] * float(
                str(r.get("rate", 0)).replace(",", "").replace("₹", "").strip() or 0
            )
            for r in results
        )
    except Exception:
        total_val = 0.0

    summary_lines = [
        f"✅ *{r['brand']} {r['spec']} {r['type']}*: -{r['quantity']} units"
        for r in results
    ]
    if errors:
        summary_lines.append("\n⚠️ *Skipped items:*")
        summary_lines.extend([f"• {e}" for e in errors])

    caption = (
        f"🚛 *Delivery Receipt*\n"
        f"Vehicle: *{vehicle_no}*\n"
        f"Total: *{total_qty} units*\n"
        f"Value: *₹{total_val:,.0f}*\n\n"
        + "\n".join(summary_lines)
    )

    await context.bot.send_document(
        chat_id=chat_id,
        document=pdf_io,
        filename=pdf_name,
        caption=caption,
        parse_mode="Markdown"
    )


# ── Add new product ──────────────────────────────────────────────
async def _handle_add_product(update, parsed, sender):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text(
            "Product ki details do.\nFormat: `naya product: Solar Panel, Waaree, 650W, DCR`",
            parse_mode="Markdown"
        )
        return

    lines = []
    for item in items:
        result = add_new_product(
            item.get("category", ""),
            item["brand"],
            item["spec"],
            item.get("type", "DCR"),
            sender
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}* add ho gaya!\n"
                f"Quantity abhi 0 hai — jab maal aaye tab update karo."
            )
        else:
            lines.append(f"❌ {result.get('error', 'Error')}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


# ── Update rate ──────────────────────────────────────────────────
async def _handle_update_rate(update, parsed):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text("Kaunsa product aur kitna rate? Dobara bhejo.")
        return

    lines = []
    for item in items:
        rate = item.get("rate", 0)
        if not rate or int(rate) <= 0:
            lines.append(f"❌ Rate missing: {item['brand']} {item['spec']}")
            continue
        result = update_rate(
            item["brand"], item["spec"], item.get("type", "DCR"), int(rate)
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*\n"
                f"Rate: *₹{int(rate):,}* per unit\n"
                f"Total ({result['quantity']} units): *₹{result['quantity'] * int(rate):,}*"
            )
        else:
            lines.append(f"❌ {result['error']}")

    await update.message.reply_text(
        "💰 *Rate Updated:*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown"
    )


# ── Error handler ────────────────────────────────────────────────
async def error_handler(update, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text(
            "⚠️ Kuch gadbad ho gayi. Thodi der mein dobara try karo."
        )


# ── Entry point ──────────────────────────────────────────────────
def main():
    import asyncio
    # Python 3.10+ no longer auto-creates an event loop — set one explicitly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    start_health_server()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info("Warehouse bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
