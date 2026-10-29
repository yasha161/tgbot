import os
import sys
import shutil
import asyncio
import tempfile
import logging
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update, InputMediaPhoto, InputMediaDocument
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_writer import generate_carousel_content, analyze_user_message
from renderer import render_carousel_slides
from asset_manager import save_user_asset, list_user_assets, resolve_assets_from_text

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Render health-check server for 100% Free Web Service hosting
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Ron Carousel Agent is alive!")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        logger.info(f"Render health-check server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")

# Store user state across chats
USER_SESSIONS = {}
USER_MEDIA_GROUPS = {}

def get_session(chat_id: int):
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = {
            "pending_photos": [],
            "pending_heading": None,
            "custom_instructions": "",
            "is_3d_mode": False,
            "special_edit": ""
        }
    return USER_SESSIONS[chat_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Arre Yash bhai! Mai hoon Ron — tera AI Carousel Partner. 🤝\n\n"
        "⚡ *Special Secret Trigger Codes*:\n"
        "• `312make <heading>`: Instant carousel render trigger (100% precision).\n"
        "• `312make #3d <heading>`: **3D Elements Mode** (Floating 3D metallic badges, glass cards & deep gold glow).\n"
        "• `987inst <instruction>`: Custom instruction lock karega (e.g. *987inst pet dhyan se cover karna*).\n"
        "• `456head <heading>`: Exact heading lock karega bina render kiye.\n"
        "• `789style 3d`: 3D mode on/off toggle karega.\n"
        "• `000status`: Memory aur photos check karega.\n"
        "• `111reset`: Sab clear karega.\n\n"
        "💾 *Memory Tags*: Photo ke caption me `#save bank` likho, future me bas `@bank` likh kar bula lo!\n\n"
        "Batao bhai, kya instruction ya topic hai?"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = get_session(chat_id)
    photos_count = len(session.get("pending_photos", []))
    saved_tags = list_user_assets(chat_id)
    tags_str = ", ".join([f"`@{t}`" for t in saved_tags]) if saved_tags else "None"
    heading = session.get("pending_heading") or "None"
    inst = session.get("custom_instructions") or "None"
    mode = "3D Luxury Mode 💎" if session.get("is_3d_mode") else "Standard Clean Studio 📸"
    
    status_text = (
        f"📊 *Ron Brain Status*:\n"
        f"• **Buffer Photos**: {photos_count}\n"
        f"• **Saved Memory Tags**: {tags_str}\n"
        f"• **Active Heading**: `{heading}`\n"
        f"• **Locked Instructions**: `{inst}`\n"
        f"• **Visual Style**: `{mode}`\n\n"
        f"Render karne ke liye bas likho `312make` ya `#make`!"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    session["pending_photos"] = []
    session["pending_heading"] = None
    session["custom_instructions"] = ""
    session["is_3d_mode"] = False
    session["special_edit"] = ""
    await update.message.reply_text("🧹 Buffer & styling reset! Naya topic aur photos bhej sakte ho.")

async def process_carousel_job(chat_id, user_images, heading, is_3d: bool, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(chat_id)
    style_label = "3D Luxury Mode (Floating Badges & Gold Glow)" if is_3d else "Standard Clean Studio"
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ *Photos process ho rahi hain... [{style_label}] shuru!*",
        parse_mode="Markdown"
    )
    
    work_dir = tempfile.mkdtemp(prefix="carousel_bot_")
    
    try:
        saved_images = []
        for i, img_item in enumerate(user_images):
            img_path = os.path.join(work_dir, f"input_{i+1}.jpg")
            if isinstance(img_item, (bytes, bytearray)):
                with open(img_path, "wb") as f:
                    f.write(img_item)
            elif isinstance(img_item, str) and os.path.exists(img_item):
                shutil.copyfile(img_item, img_path)
            saved_images.append(img_path)
            
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✍️ *Gemini 2.5 Flash copy likh raha hai (1-2 lines crisp)...*\nHeading: `{heading}`",
            parse_mode="Markdown"
        )
        
        loop = asyncio.get_event_loop()
        content_data = await loop.run_in_executor(
            None,
            generate_carousel_content,
            heading,
            saved_images,
            session.get("custom_instructions", "")
        )
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🎨 *Playwright 5 slides render kar raha hai (Face Safe + Strategic Midriff Cover)...*",
            parse_mode="Markdown"
        )
        
        png_slides = await render_carousel_slides(content_data, saved_images, work_dir, is_3d, session.get("special_edit", ""))
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🚀 *Slides ready! Telegram album me upload kar raha hoon...*",
            parse_mode="Markdown"
        )
        
        media_group = []
        for i, slide_path in enumerate(png_slides):
            caption = f"Slide {i+1} of 5" if i == 0 else None
            with open(slide_path, "rb") as f:
                media_group.append(InputMediaPhoto(f.read(), caption=caption))
                
        await context.bot.send_media_group(chat_id=chat_id, media=media_group)
        
        doc_group = []
        for i, slide_path in enumerate(png_slides):
            with open(slide_path, "rb") as f:
                doc_group.append(InputMediaDocument(f.read(), filename=f"slide_{i+1}.png"))
        await context.bot.send_media_group(chat_id=chat_id, media=doc_group)
        
        session["pending_photos"] = []
        session["pending_heading"] = None
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ *Bhai carousel ready hai!* Check karo aur batao kaisa laga. Instagram par post karne ke liye 100% compliant hai! 📌",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error during carousel creation: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Arre bro, render me issue aaya: {str(e)}"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    session = get_session(chat_id)
    
    photo = msg.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = await photo_file.download_as_bytearray()
    
    media_group_id = msg.media_group_id
    caption = (msg.caption or "").strip()
    caption_lower = caption.lower()
    
    # Check save tag
    if "#save" in caption_lower or "save as" in caption_lower or caption_lower.startswith("save "):
        parts = caption.replace("#save", "").replace("save as", "").replace("save", "").strip().split()
        if parts:
            save_tag = parts[0]
            saved_name = save_user_asset(chat_id, save_tag, photo_bytes)
            await msg.reply_text(f"💾 *Photo saved as `@{saved_name}`!* 📸\n\nAb future me bas `@{saved_name}` likh dena, mai memory se le lunga!")
            return

    # Check 312make trigger in caption
    is_3d = ("#3d" in caption_lower) or ("3d" in caption_lower) or session.get("is_3d_mode", False)
    has_make_trigger = ("312make" in caption_lower) or ("#make" in caption_lower) or ("#banao" in caption_lower)
    
    if media_group_id:
        if media_group_id not in USER_MEDIA_GROUPS:
            USER_MEDIA_GROUPS[media_group_id] = {
                "photos": [photo_bytes],
                "caption": caption,
                "chat_id": chat_id
            }
            await asyncio.sleep(2.5)
            group_data = USER_MEDIA_GROUPS.pop(media_group_id, None)
            if group_data:
                photos = group_data["photos"]
                final_caption = group_data["caption"]
                session["pending_photos"].extend(photos)
                count = len(session["pending_photos"])
                
                final_lower = final_caption.lower()
                is_3d_final = ("#3d" in final_lower) or ("3d" in final_lower) or session.get("is_3d_mode", False)
                trigger_final = ("312make" in final_lower) or ("#make" in final_lower) or ("#banao" in final_lower)
                
                if trigger_final:
                    heading = final_caption.replace("312make", "").replace("#make", "").replace("#banao", "").replace("#3d", "").strip()
                    if not heading:
                        heading = session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
                    await process_carousel_job(chat_id, session["pending_photos"], heading, is_3d_final, context)
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"📸 *{len(photos)} photos receive ho gayi bhai!* (Total: {count})\n\nJab render karna ho, bas likho `312make <heading>` ya normal baat karo!",
                        parse_mode="Markdown"
                    )
        else:
            USER_MEDIA_GROUPS[media_group_id]["photos"].append(photo_bytes)
            if caption:
                USER_MEDIA_GROUPS[media_group_id]["caption"] = caption
    else:
        session["pending_photos"].append(photo_bytes)
        count = len(session["pending_photos"])
        
        if has_make_trigger:
            heading = caption.replace("312make", "").replace("#make", "").replace("#banao", "").replace("#3d", "").strip()
            if not heading:
                heading = session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
            await process_carousel_job(chat_id, session["pending_photos"], heading, is_3d, context)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📸 *Photo save ho gayi!* (Total: {count} photo)\n\nJab banana ho, bas `312make <heading>` likh dena!",
                parse_mode="Markdown"
            )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    raw_text = msg.text.strip()
    lower_text = raw_text.lower()
    session = get_session(chat_id)
    
    # 1. Secret Reset Code: 111reset or /clear
    if lower_text in ["111reset", "/clear", "#clear", "clear"]:
        await clear_command(update, context)
        return
        
    # 2. Secret Status Code: 000status or /status
    if lower_text in ["000status", "/status", "#status", "status"]:
        await status_command(update, context)
        return
        
    # 3. Assets list: /assets
    if lower_text in ["/assets", "#assets", "assets"]:
        tags = list_user_assets(chat_id)
        tags_str = ", ".join([f"`@{t}`" for t in tags]) if tags else "None"
        await update.message.reply_text(f"📁 *Saved Memory Tags*: {tags_str}\n\nPrompt me `@tag` likhoge toh mai direct use kar lunga!")
        return

    # 4. Secret Instruction Code: 987inst <instruction>
    if lower_text.startswith("987inst") or lower_text.startswith(("#inst", "/inst")):
        inst_text = raw_text.replace("987inst", "").replace("#inst", "").replace("/inst", "").strip()
        session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst_text}".strip(" |")
        await update.message.reply_text(f"🔒 *Instruction Locked [987inst]*: `{inst_text}`\n\nAgle carousels me ye strictly apply hoga!", parse_mode="Markdown")
        return

    # 5. Secret Heading Code: 456head <heading>
    if lower_text.startswith("456head") or lower_text.startswith(("#heading", "/heading")):
        head_text = raw_text.replace("456head", "").replace("#heading", "").replace("/heading", "").strip()
        session["pending_heading"] = head_text
        await update.message.reply_text(f"📌 *Heading Locked [456head]*: `{head_text}`\n\nAb jab bhi `312make` likhoge, ye exact heading use hogi!", parse_mode="Markdown")
        return

    # 6. Secret Style Code: 789style 3d / #3d
    if lower_text.startswith("789style") or lower_text in ["#3d", "3d mode", "special edit"]:
        if "3d" in lower_text:
            session["is_3d_mode"] = True
            await update.message.reply_text("💎 *3D Luxury Style Activated [789style]*!\nFloating metallic badges, 3D perspective glass cards aur deep gold glow use honge.")
        else:
            session["is_3d_mode"] = False
            await update.message.reply_text("📸 *Standard Studio Style Set*!")
        return

    # Check for saved asset codewords in text (@bank, @uncle)
    resolved_paths = resolve_assets_from_text(chat_id, raw_text)
    if resolved_paths:
        for p in resolved_paths:
            if p not in session["pending_photos"]:
                session["pending_photos"].append(p)

    # 7. Secret Trigger Make Code: 312make [heading]
    is_312make = lower_text.startswith("312make") or lower_text.startswith(("#make", "#banao", "/make", "/banao"))
    
    if is_312make:
        photos = session.get("pending_photos", [])
        if len(photos) == 0:
            await update.message.reply_text("⚠️ Bhai photos nahi aayi abhi! 1 se 4 photos bhej do (ya saved memory tag jaise `@bank` likho), fir `312make` bolo.")
            return
            
        is_3d = ("#3d" in lower_text) or ("3d" in lower_text) or session.get("is_3d_mode", False)
        
        # Clean heading
        heading = raw_text
        for prefix in ["312make", "#make", "#banao", "/make", "/banao", "#3d"]:
            heading = heading.replace(prefix, "")
        heading = heading.strip() or session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
        
        mode_text = "💎 3D Luxury Elements" if is_3d else "📸 Standard Studio"
        await update.message.reply_text(f"🚀 *Work Triggered [312make]*\nHeading: `{heading}`\nStyle: `{mode_text}`\n\nRender shuru ho raha hai...", parse_mode="Markdown")
        await process_carousel_job(chat_id, photos, heading, is_3d, context)
        return

    # 8. Otherwise: 100% Normal Friendly Chat (Gemini 2.5 Flash Brain)
    ctx = {
        "photos_count": len(session.get("pending_photos", [])),
        "active_heading": session.get("pending_heading"),
        "instructions": session.get("custom_instructions")
    }
    
    analysis = await asyncio.get_event_loop().run_in_executor(
        None, analyze_user_message, chat_id, raw_text, ctx
    )
    
    intent = analysis.get("intent", "CHAT")
    reply = analysis.get("reply", "Haan bhai!")
    extracted_inst = analysis.get("extracted_instruction")
    extracted_heading = analysis.get("extracted_heading")
    
    if extracted_heading:
        session["pending_heading"] = extracted_heading
        
    if intent == "INSTRUCTION":
        if extracted_inst:
            session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {extracted_inst}".strip(" |")
        await update.message.reply_text(reply)
        return
    elif intent == "TRIGGER_MAKE":
        photos = session.get("pending_photos", [])
        if len(photos) == 0:
            await update.message.reply_text(f"{reply}\n\n⚠️ Lekin pehle **photo bhej do**, fir turant bana dunga!")
            return
        final_heading = extracted_heading or session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
        await update.message.reply_text(reply)
        await process_carousel_job(chat_id, photos, final_heading, session.get("is_3d_mode", False), context)
        return
    else:
        await update.message.reply_text(reply)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment!")
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info("Ron Carousel Agent (Secret Codes + 3D Mode) is live on Telegram! Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
