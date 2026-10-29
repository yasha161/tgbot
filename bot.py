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

from ai_writer import generate_carousel_content, chat_with_agent
from renderer import render_carousel_slides

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
        "Arre bro! Mai hoon Ron — tera AI Carousel Partner. 🤝\n\n"
        "Hum bilkul waise hi kaam karenge jaise Antigravity ke sath karte ho — friendly, smart aur high-speed!\n\n"
        "💬 *Normal Chat Mode*:\n"
        "Jab tak tum special command nahi doge, mai aapse dost ki tarah baat karunga, ideas discuss karunga aur sawaalon ke jawab dunga.\n\n"
        "⚡ *Special Commands (Work Mode)*:\n"
        "• `#make <heading>` ya `#banao <heading>`: 4:5 studio carousel generate karega.\n"
        "• `#inst <instruction>`: Custom instruction lock karega (e.g. *#inst text 1 line hi rakhna*).\n"
        "• `#heading <text>`: Exact heading set karega.\n"
        "• `#status`: Check karega kitni photos aur kya instructions save hain.\n"
        "• `#clear`: Naye project ke liye buffer reset karega.\n\n"
        "📸 *Quick Flow*:\n"
        "1. Photos bhej do (1 se 4+ photos).\n"
        "2. Likho `#make <aapka topic>` (e.g. `#make Being a daughter of a mutual fund distributor...`).\n"
        "3. Live 5-slide carousel album + documents deliver ho jayenge! 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    photos_count = len(session.get("pending_photos", []))
    heading = session.get("pending_heading") or "None (default will be used)"
    inst = session.get("custom_instructions") or "None"
    
    status_text = (
        f"📊 *Current Status*:\n"
        f"• **Saved Photos**: {photos_count}\n"
        f"• **Active Heading**: `{heading}`\n"
        f"• **Custom Instructions**: `{inst}`\n\n"
        f"Ready to render? Bas `#make` ya `#banao` bhej do!"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    session["pending_photos"] = []
    session["pending_heading"] = None
    session["custom_instructions"] = ""
    await update.message.reply_text("🧹 Buffer cleared! Naya topic aur photos bhej sakte ho.")

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
        for i, img_bytes in enumerate(user_images):
            img_path = os.path.join(work_dir, f"input_{i+1}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            saved_images.append(img_path)
            
        # Step 2: Generate 1-2 line crisp copy using exact user heading
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✍️ *Gemini 2.5 Flash copy likh raha hai (1-2 lines crisp)...*\nExact Heading: `{heading}`",
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
            text="🎨 *Playwright 5 slides render kar raha hai (4-Photo Combo + Strategic Midriff Cover)...*",
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
        
        # Clear photos buffer after successful render
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
    caption = msg.caption or ""
    
    # Check if caption contains trigger code word
    trigger_words = ["#make", "#banao", "#render", "/make", "/banao", "/render"]
    has_trigger = any(t in caption.lower() for t in trigger_words)
    
    if media_group_id:
        if media_group_id not in USER_MEDIA_GROUPS:
            USER_MEDIA_GROUPS[media_group_id] = {
                "photos": [photo_bytes],
                "caption": caption,
                "chat_id": chat_id
            }
            # Wait for all photos in album to arrive
            await asyncio.sleep(2.5)
            group_data = USER_MEDIA_GROUPS.pop(media_group_id, None)
            if group_data:
                photos = group_data["photos"]
                final_caption = group_data["caption"]
                
                # Add to session
                session["pending_photos"].extend(photos)
                count = len(session["pending_photos"])
                
                # Check trigger
                caption_lower = final_caption.lower()
                trigger_match = None
                for t in trigger_words:
                    if t in caption_lower:
                        trigger_match = t
                        break
                        
                if trigger_match:
                    # Clean heading
                    heading = final_caption.replace(trigger_match, "").strip()
                    if not heading:
                        heading = "Being a daughter of a mutual fund distributor, I know one thing…"
                    await process_carousel_job(chat_id, session["pending_photos"], heading, context)
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"📸 *{len(photos)} photos receive ho gayi bro!* (Total: {count})\n\nAbhi normal chat on hai. Jab finalize ho jaye, bas `#make <heading>` ya `#banao <heading>` bhej dena!",
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
        
        caption_lower = caption.lower()
        trigger_match = None
        for t in trigger_words:
            if t in caption_lower:
                trigger_match = t
                break
                
        if trigger_match:
            heading = caption.replace(trigger_match, "").strip()
            if not heading:
                heading = "Being a daughter of a mutual fund distributor, I know one thing…"
            await process_carousel_job(chat_id, session["pending_photos"], heading, context)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📸 *Photo save ho gayi!* (Total: {count} photos)\n\nJab aur photos bhejni ho bhej do. Render ke liye bas `#make <heading>` ya `#banao` bol dena!",
                parse_mode="Markdown"
            )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    raw_text = msg.text.strip()
    lower_text = raw_text.lower()
    session = get_session(chat_id)
    
    # 1. Check for #clear or /clear
    if lower_text in ["#clear", "/clear", "clear"]:
        await clear_command(update, context)
        return
        
    # 2. Check for #status or /status
    if lower_text in ["#status", "/status", "status"]:
        await status_command(update, context)
        return
        
    # 3. Check for #inst or /inst or instruction
    if lower_text.startswith(("#inst", "/inst")):
        inst_text = raw_text.split(" ", 1)[1] if " " in raw_text else ""
        session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst_text}".strip(" |")
        await update.message.reply_text(f"🔒 *Instruction locked*: `{inst_text}`\n\nAgle carousels me ye dhyan rakhunga!", parse_mode="Markdown")
        return
        
    # 4. Check for #heading or /heading
    if lower_text.startswith(("#heading", "/heading")):
        heading_text = raw_text.split(" ", 1)[1] if " " in raw_text else ""
        session["pending_heading"] = heading_text
        await update.message.reply_text(f"📌 *Heading locked*: `{heading_text}`\n\nAb jab bhi `#make` ya `#banao` likhoge, ye exact heading use hogi!", parse_mode="Markdown")
        return

    # 5. Check for Trigger Words: #make, #banao, #render
    trigger_words = ["#make", "#banao", "#render", "/make", "/banao", "/render"]
    matched_trigger = None
    for t in trigger_words:
        if lower_text.startswith(t) or lower_text == t:
            matched_trigger = t
            break
            
    if matched_trigger:
        # Check if photos exist
        if len(session["pending_photos"]) == 0:
            await update.message.reply_text("Arre bro, heading/trigger toh mil gaya par photos nahi aayi abhi! 4 photos bhej do, fir `#make` bolna.")
            return
            
        # Extract heading from command if provided
        cmd_heading = raw_text[len(matched_trigger):].strip()
        final_heading = cmd_heading or session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
        
        await update.message.reply_text(f"🚀 *Work Mode Triggered!*\nHeading: `{final_heading}`\n\nRender shuru kar raha hoon...", parse_mode="Markdown")
        await process_carousel_job(chat_id, session["pending_photos"], final_heading, context)
        return

    # 6. Default: 100% Normal Friendly Chat (Antigravity Persona)
    reply = await asyncio.get_event_loop().run_in_executor(
        None, chat_with_agent, chat_id, raw_text
    )
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
    
    logger.info("Ron Carousel Agent (Special Commands Mode) is live on Telegram! Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
