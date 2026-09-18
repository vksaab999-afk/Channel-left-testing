import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(level=logging.INFO)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

# Multiple Admins Support
ADMIN_IDS = [5785924075, 8802096404]

# MongoDB Atlas URI
MONGO_URI = os.environ.get("MONGO_URI")

# Source Chat & Retention Settings
SOURCE_CHAT_ID = int(os.environ.get("STORAGE_CHAT_ID", "5785924075"))
TARGET_MSG_ID = 49  # Message ID 49

# Custom Emoji IDs for Buttons
EMOJI_JOIN = "4990182601252668309"
EMOJI_RECOVERY = "6111716252932119427"
# =======================================================

# --- MONGODB SETUP ---
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_bot_db"]
users_collection = db["users"]

def save_user_to_mongo(user_id, first_name, username):
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "first_name": first_name or "",
                    "username": username or ""
                }
            },
            upsert=True
        )
    except Exception as e:
        logging.error(f"MongoDB Error: {e}")

# --- KEEP-ALIVE WEB SERVER FOR RENDER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><body><h1>Bot is Live and MongoDB Connected!</h1></body></html>", "utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    
    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- STYLED BUTTON HELPER ---
def styled_button(text, *, style, icon_custom_emoji_id=None, url=None, callback_data=None):
    action = {"url": url} if url else {"callback_data": callback_data or "noop"}
    modern = {"text": text, **action, "style": style}
    if icon_custom_emoji_id:
        modern["icon_custom_emoji_id"] = icon_custom_emoji_id

    try:
        return InlineKeyboardButton(**modern)
    except TypeError:
        api_kwargs = {"style": style}
        if icon_custom_emoji_id:
            api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
        try:
            return InlineKeyboardButton(text=text, api_kwargs=api_kwargs, **action)
        except TypeError:
            return InlineKeyboardButton(text=text, **action)

# --- JOIN REQUEST HANDLER ---
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    logging.info(f"User {user.id} saved on Join Request.")

# --- MEMBER LEFT HANDLER ---
async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    if old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
        user = result.from_user
        user_id = user.id

        saved_user = users_collection.find_one({"user_id": user_id})
        
        if saved_user:
            try:
                retention_keyboard = [
                    [styled_button(" JOIN CHANNEL", style="success", icon_custom_emoji_id=EMOJI_JOIN, url="https://t.me/+QiuG0TOuhe81MTI1")],
                    [styled_button(" LOSS RECOVERY", style="danger", icon_custom_emoji_id=EMOJI_RECOVERY, url="https://t.me/m/wbdDfR5tZTI1")]
                ]
                reply_markup = InlineKeyboardMarkup(retention_keyboard)

                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=SOURCE_CHAT_ID,
                    message_id=TARGET_MSG_ID,
                    reply_markup=reply_markup
                )
                logging.info(f"Retention Msg 49 sent to {user_id}")
            except Exception as e:
                logging.error(f"Error sending DM to left user {user_id}: {e}")

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    await update.message.reply_text("👋 Welcome!")

# --- BROADCAST LOGIC ---
async def execute_broadcast(message_to_broadcast, context, admin_chat_id):
    users = list(users_collection.find({"user_id": {"$nin": ADMIN_IDS}}, {"user_id": 1}))
    total_users = len(users)

    if total_users == 0:
        await context.bot.send_message(chat_id=admin_chat_id, text="⚠️ Database me aur koi user nahi hai!")
        return

    for u in users:
        u_id = u["user_id"]
        try:
            if message_to_broadcast.text:
                await context.bot.send_message(chat_id=u_id, text=message_to_broadcast.text, entities=message_to_broadcast.entities)
            elif message_to_broadcast.photo:
                await context.bot.send_photo(chat_id=u_id, photo=message_to_broadcast.photo[-1].file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.video:
                await context.bot.send_video(chat_id=u_id, video=message_to_broadcast.video.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.audio:
                await context.bot.send_audio(chat_id=u_id, audio=message_to_broadcast.audio.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.voice:
                await context.bot.send_voice(chat_id=u_id, voice=message_to_broadcast.voice.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.document:
                await context.bot.send_document(chat_id=u_id, document=message_to_broadcast.document.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            
            await asyncio.sleep(0.04)
        except Exception as e:
            logging.error(f"Error sending to {u_id}: {e}")

    await context.bot.send_message(
        chat_id=admin_chat_id, 
        text="✅ Broadcast Completed!", 
        parse_mode="Markdown"
    )

# --- AUTOMATIC BROADCAST ---
async def auto_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return
    if msg.text and msg.text.startswith("/"):
        return
    await execute_broadcast(msg, context, update.effective_user.id)

# --- COMMAND BROADCAST ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return

    if msg.reply_to_message:
        await execute_broadcast(msg.reply_to_message, context, update.effective_user.id)
    else:
        text_after_command = msg.text.replace("/broadcast", "").strip()
        if text_after_command:
            users = list(users_collection.find({"user_id": {"$nin": ADMIN_IDS}}, {"user_id": 1}))
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=text_after_command)
                    await asyncio.sleep(0.04)
                except:
                    pass
            await msg.reply_text("✅ Broadcast Completed!")
        else:
            await msg.reply_text("⚠️ Message ke sath /broadcast likhein ya kisi msg par reply karein.")

# --- STATS COMMAND ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        total_users = users_collection.count_documents({})
        await update.message.reply_text(f"📊 **Total Users:** `{total_users}`", parse_mode="Markdown")

# --- ASYNC MAIN RUNNER (Fixes Python 3.14 Event Loop Crash) ---
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(ChatMemberHandler(handle_member_left, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.User(ADMIN_IDS) & ~filters.COMMAND, auto_broadcast))

    print("Bot is running smoothly...")
    
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "chat_join_request", "chat_member"], drop_pending_updates=True)
        # Keeps bot running indefinitely
        await asyncio.Event().wait()

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())
