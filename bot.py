import os
import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

# Render Port Keep-Alive Web Server
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running Alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# ==================== CONFIGURATION ====================
# Render ke Environment Variables se token fetch hoga
BOT_TOKEN = os.getenv("BOT_TOKEN")
# =======================================================

async def get_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id
        
        reply_text = (
            f"✅ **Message ID Extracted!**\n\n"
            f"🆔 **CHAT_ID:** `{chat_id}`\n"
            f"📩 **MSG_ID:** `{msg_id}`"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")

async def main_async():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing hai! Please Render ke Environment variables mein 'BOT_TOKEN' set karein.")

    # Background me web server start hoga Render ke liye
    Thread(target=run_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, get_ids))
    
    print("Bot is active and polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Bot ko chalu rakhne ke liye
    stop_signal = asyncio.Event()
    await stop_signal.wait()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
