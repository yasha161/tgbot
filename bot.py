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
            "custom_instructions": ""
        }
    return USER_SESSIONS[chat_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Arre Yash bhai! Mai hoon Ron — tera personal AI Carousel Creator. 🤝\n\n"
        "✨ *Kya-kya kar sakta hoon mai*:\n"
        "• **1 Photo Se Bhi 5 Slides**: Sirf 1 photo doge toh bhi hero cover + floating glass cards ke sath luxury carousel banega.\n"
        "• **Photo Codewords / Memory**: Photo bhejte time caption me `#save bank` ya `#save uncle` likh do — mai hamesha ke liye save kar lunga. Future me bas `@bank` likhoge aur mai seedha memory se utha lunga!\n"
        "• **Smart Intent Brain**: Mujhse dost ki tarah baat karo, instructions do (e.g. *'text 1 line rakhna'*, *'pet dhyan se cover karna'*), mai turant lock kar lunga.\n"
        "• **Work Command**: Jab finalize ho, bas bolo *'bana do'*, *'make it'*, ya *'#make <heading>'*!\n\n"
        "Batao bhai, aaj kiska carousel banana hai?"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def assets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    tags = list_user_assets(chat_id)
    if not tags:
        await update.message.reply_text("Abhi koi photo codeword me save nahi hai bro! Photo bhejte waqt caption me `#save <name>` likh do (jaise `#save bank` ya `#save uncle`).")
    else:
        tags_str = ", ".join([f"`@{t}`" for t in tags])
        await update.message.reply_text(f"📁 *Aapki Saved Photos*: {tags_str}\n\nFuture me bas prompt me `@tag` likh dena, mai memory se le lunga!")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    session["pending_photos"] = []
    session["pending_heading"] = None
    session["custom_instructions"] = ""
    await update.message.reply_text("🧹 Buffer cleared! Naya topic aur photos bhej sakte ho.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = get_session(chat_id)
    photos_count = len(session.get("pending_photos", []))
    saved_tags = list_user_assets(chat_id)
    tags_str = ", ".join([f"`@{t}`" for t in saved_tags]) if saved_tags else "None"
    heading = session.get("pending_heading") or "None"
    inst = session.get("custom_instructions") or "None"
    
    status_text = (
        f"📊 *Ron Brain Status*:\n"
        f"• **Buffer Photos**: {photos_count}\n"
        f"• **Saved Memory Tags**: {tags_str}\n"
        f"• **Active Heading**: `{heading}`\n"
        f"• **Locked Instructions**: `{inst}`\n\n"
        f"Render karne ke liye bas bolo *'bana do'*!"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def process_carousel_job(chat_id, user_images, heading, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(chat_id)
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ *Photos process ho rahi hain... Face detection, natural 4:5 framing & studio polish shuru!*",
        parse_mode="Markdown"
    )
    
    work_dir = tempfile.mkdtemp(prefix="carousel_bot_")
    
    try:
        # Step 1: Save images to temp work_dir
        saved_images = []
        for i, img_item in enumerate(user_images):
            img_path = os.path.join(work_dir, f"input_{i+1}.jpg")
            if isinstance(img_item, (bytes, bytearray)):
                with open(img_path, "wb") as f:
                    f.write(img_item)
            elif isinstance(img_item, str) and os.path.exists(img_item):
                shutil.copyfile(img_item, img_path)
            saved_images.append(img_path)
            
        # Step 2: Generate 1-2 line crisp copy using exact user heading & locked instructions
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
        
        # Step 3: Render 1080x1350 Slides with Playwright
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🎨 *Playwright 5 slides render kar raha hai (Studio Quality + Strategic Midriff Cover)...*",
            parse_mode="Markdown"
        )
        
        png_slides = await render_carousel_slides(content_data, saved_images, work_dir)
        
        # Step 4: Upload Media Album
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
        
        # Step 5: Send uncompressed PNG documents for lossless quality
        doc_group = []
        for i, slide_path in enumerate(png_slides):
            with open(slide_path, "rb") as f:
                doc_group.append(InputMediaDocument(f.read(), filename=f"slide_{i+1}.png"))
        await context.bot.send_media_group(chat_id=chat_id, media=doc_group)
        
        # Clear buffer
        session["pending_photos"] = []
        session["pending_heading"] = None
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ *Bhai carousel ready hai!* Check karo aur batao kaisa laga. Instagram par post karne ke liye ekdum mast hai! 📌",
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
    
    # Check if user wants to save this photo with a codeword (e.g. #save bank or save bank)
    caption_lower = caption.lower()
    save_tag = None
    if "#save" in caption_lower or "save as" in caption_lower or caption_lower.startswith("save "):
        parts = caption.replace("#save", "").replace("save as", "").replace("save", "").strip().split()
        if parts:
            save_tag = parts[0]
            saved_name = save_user_asset(chat_id, save_tag, photo_bytes)
            await msg.reply_text(f"💾 *Photo saved in memory as `@{saved_name}`!* 📸\n\nAb future me bas `@{saved_name}` likh dena, mai bina dobara maange photo le lunga!")
            return
            
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
                
                if final_caption:
                    ctx = {
                        "photos_count": count,
                        "active_heading": session.get("pending_heading"),
                        "instructions": session.get("custom_instructions")
                    }
                    analysis = await asyncio.get_event_loop().run_in_executor(
                        None, analyze_user_message, chat_id, final_caption, ctx
                    )
                    if analysis.get("intent") == "TRIGGER_MAKE":
                        heading = analysis.get("extracted_heading") or session.get("pending_heading") or final_caption
                        await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply", "Chalo shuru karte hain bhai! 🚀"))
                        await process_carousel_job(chat_id, session["pending_photos"], heading, context)
                        return
                    elif analysis.get("intent") == "INSTRUCTION":
                        inst = analysis.get("extracted_instruction")
                        session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst}".strip(" |")
                        await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply"))
                        return
                        
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📸 *{len(photos)} photos mil gayi bhai!* (Total: {count})\n\nKoi instruction dena ho toh batao, ya seedha bolo *'bana do'*!",
                    parse_mode="Markdown"
                )
        else:
            USER_MEDIA_GROUPS[media_group_id]["photos"].append(photo_bytes)
            if caption:
                USER_MEDIA_GROUPS[media_group_id]["caption"] = caption
    else:
        # Single photo sent
        session["pending_photos"].append(photo_bytes)
        count = len(session["pending_photos"])
        
        if caption:
            ctx = {
                "photos_count": count,
                "active_heading": session.get("pending_heading"),
                "instructions": session.get("custom_instructions")
            }
            analysis = await asyncio.get_event_loop().run_in_executor(
                None, analyze_user_message, chat_id, caption, ctx
            )
            if analysis.get("intent") == "TRIGGER_MAKE":
                heading = analysis.get("extracted_heading") or session.get("pending_heading") or caption
                await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply", "Chalo shuru karte hain bhai! 🚀"))
                await process_carousel_job(chat_id, session["pending_photos"], heading, context)
                return
            elif analysis.get("intent") == "INSTRUCTION":
                inst = analysis.get("extracted_instruction")
                session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst}".strip(" |")
                await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply"))
                return
                
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📸 *Photo save ho gayi!* (Total: {count} photo)\n\nSirf isi 1 photo pe banana hai toh bolo *'bana do'*, ya aur photos bhej sakte ho!",
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    raw_text = msg.text.strip()
    session = get_session(chat_id)
    
    if raw_text.lower() in ["/clear", "#clear", "clear"]:
        await clear_command(update, context)
        return
    if raw_text.lower() in ["/status", "#status", "status"]:
        await status_command(update, context)
        return
    if raw_text.lower() in ["/assets", "#assets", "assets"]:
        await assets_command(update, context)
        return
        
    # Check if user mentioned saved asset codewords (e.g. @bank, @uncle)
    resolved_paths = resolve_assets_from_text(chat_id, raw_text)
    if resolved_paths:
        for p in resolved_paths:
            if p not in session["pending_photos"]:
                session["pending_photos"].append(p)
                
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
            await update.message.reply_text(f"{reply}\n\n⚠️ Lekin pehle **photo bhej do** (ya kisi saved tag jaise `@bank` ko mention karo), fir turant bana dunga!")
            return
            
        final_heading = extracted_heading or session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
        await update.message.reply_text(reply)
        await process_carousel_job(chat_id, photos, final_heading, context)
        return
        
    else:
        # Casual chat
        await update.message.reply_text(reply)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment!")
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("assets", assets_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info("Ron Carousel Agent (Full Upgrades + Asset Memory) is live on Telegram! Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
