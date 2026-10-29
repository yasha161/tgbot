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
        "Mujhme **Gemini 2.5 Flash** ki full intelligence loaded hai:\n\n"
        "💬 *Smart Chat & Brain*:\n"
        "• **Normal Baat Karo**: Kisi bhi cheez pe discuss karo, mai Antigravity ki tarah jawab dunga.\n"
        "• **Instructions Do**: Koi bhi rule bolo (e.g. *'bhai pet cover dhyan se karna'*, *'text 1 line hi rakhna'*), mai turant samajh kar lock kar lunga.\n"
        "• **Work Command**: Jab bhi bolo *'bana do'*, *'start karo'*, ya *'#make'*, mai instantly high-res carousel render kar dunga! 🚀\n\n"
        "📸 **Bas photos bhej do aur baat shuru karo!**"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    photos_count = len(session.get("pending_photos", []))
    heading = session.get("pending_heading") or "None (default wealth wisdom will be used)"
    inst = session.get("custom_instructions") or "None"
    
    status_text = (
        f"📊 *Current Brain Status*:\n"
        f"• **Saved Photos**: {photos_count}\n"
        f"• **Active Heading**: `{heading}`\n"
        f"• **Locked Instructions**: `{inst}`\n\n"
        f"Ready to render? Bas bolo *'bana do'* ya *'#make'*!"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.chat_id)
    session["pending_photos"] = []
    session["pending_heading"] = None
    session["custom_instructions"] = ""
    await update.message.reply_text("🧹 Buffer & memory cleared! Naya topic aur photos bhej sakte ho.")

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
                session["pending_photos"].extend(photos)
                count = len(session["pending_photos"])
                
                # Analyze caption with Gemini
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
                        await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply", "Chalo shuru karte hain! 🚀"))
                        await process_carousel_job(chat_id, session["pending_photos"], heading, context)
                        return
                    elif analysis.get("intent") == "INSTRUCTION":
                        inst = analysis.get("extracted_instruction")
                        session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst}".strip(" |")
                        await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply"))
                        return
                        
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📸 *{len(photos)} photos mil gayi bro!* (Total: {count})\n\nKoi instruction dena ho toh batao, ya seedha bolo *'bana do'* / *'#make <heading>'*!",
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
                await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply", "Chalo shuru karte hain! 🚀"))
                await process_carousel_job(chat_id, session["pending_photos"], heading, context)
                return
            elif analysis.get("intent") == "INSTRUCTION":
                inst = analysis.get("extracted_instruction")
                session["custom_instructions"] = f"{session.get('custom_instructions', '')} | {inst}".strip(" |")
                await context.bot.send_message(chat_id=chat_id, text=analysis.get("reply"))
                return
                
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📸 *Photo save ho gayi!* (Total: {count} photos)\n\nJab aur photos bhejni ho bhej do, ya bolo *'bana do'*!",
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    raw_text = msg.text.strip()
    session = get_session(chat_id)
    
    # 1. Quick commands
    if raw_text.lower() in ["/clear", "#clear", "clear"]:
        await clear_command(update, context)
        return
    if raw_text.lower() in ["/status", "#status", "status"]:
        await status_command(update, context)
        return
        
    # 2. Run through Gemini 2.5 Flash intelligence
    ctx = {
        "photos_count": len(session.get("pending_photos", [])),
        "active_heading": session.get("pending_heading"),
        "instructions": session.get("custom_instructions")
    }
    
    analysis = await asyncio.get_event_loop().run_in_executor(
        None, analyze_user_message, chat_id, raw_text, ctx
    )
    
    intent = analysis.get("intent", "CHAT")
    reply = analysis.get("reply", "Haan bro!")
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
        if len(session["pending_photos"]) == 0:
            await update.message.reply_text(f"{reply}\n\n⚠️ Lekin pehle **photos bhej do** (1 se 4 photos), fir render shuru kar dunga!")
            return
            
        final_heading = extracted_heading or session.get("pending_heading") or "Being a daughter of a mutual fund distributor, I know one thing…"
        await update.message.reply_text(reply)
        await process_carousel_job(chat_id, session["pending_photos"], final_heading, context)
        return
        
    else:
        # Normal chat
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
    
    logger.info("Ron Carousel Agent (Full Gemini Intelligence) is live on Telegram! Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
