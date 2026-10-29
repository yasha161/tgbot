import os
import sys
import shutil
import asyncio
import tempfile
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Guarantee loading .env from bot directory
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_FILE)

from telegram import Update, InputMediaPhoto, InputMediaDocument
from telegram.request import HTTPXRequest
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
from memory_store import (
    load_user_memory,
    save_pending_photo,
    get_pending_photos,
    clear_pending_photos,
    set_active_heading,
    get_active_heading,
    set_3d_mode,
    get_3d_mode,
    update_visual_directives,
    get_visual_directives,
    get_user_guidelines_str,
    update_user_guidelines,
    reset_user_session,
    set_custom_script,
    get_custom_script,
    clear_custom_script
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Render health-check server for 100% Free Web Service hosting
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Ron Executive Carousel Agent is alive!")
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

USER_MEDIA_GROUPS = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "**Ron — Executive Art Director & Carousel Engine**\n\n"
        "Ready to produce high-retention 4:5 Instagram Carousels (1080×1350).\n\n"
        "**How to Work With Me**:\n"
        "• **Natural Conversation**: Talk normally in Hindi or English (e.g. *'bhai purani chat padh ke carousel bana do'*, *'1 photo use karna'*, *'floating icon chahiye'*, *'text beech me rakhna'*).\n"
        "• **Photo Flexibility**: Send 1 photo for a high-impact single hero cover, or 4 photos for an editorial 2×2 combo cover.\n"
        "• **Codewords (Optional shortcuts)**:\n"
        "  - `312make <heading>`: Instant render.\n"
        "  - `312make #3d`: Render with 3D luxury glass styling.\n"
        "  - `987inst <guideline>`: Lock rules into persistent memory.\n"
        "  - `456head <heading>`: Set heading without rendering.\n"
        "  - `000status`: Review active session & memory.\n"
        "  - `111reset`: Clear current session.\n\n"
        "• **Asset Tagging**: Send any photo with `#save <tag>` (e.g. `#save bank`), and tag `@bank` anytime in chat.\n\n"
        "Drop photos or a topic whenever you're ready."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    pending = get_pending_photos(chat_id)
    saved_tags = list_user_assets(chat_id)
    tags_str = ", ".join([f"`@{t}`" for t in saved_tags]) if saved_tags else "None"
    heading = get_active_heading(chat_id) or "None"
    guidelines = get_user_guidelines_str(chat_id) or "None"
    is_3d = get_3d_mode(chat_id)
    directives = get_visual_directives(chat_id)
    
    status_text = (
        f"**Session & Memory Overview**:\n"
        f"• **Buffered Photos on Disk**: {len(pending)}\n"
        f"• **Saved Memory Tags**: {tags_str}\n"
        f"• **Active Heading**: `{heading}`\n"
        f"• **Persistent Guidelines**: `{guidelines}`\n"
        f"• **Visual Mode**: `{'3D Luxury Mode 💎' if is_3d else 'Standard Studio 📸'}`\n"
        f"• **Floating Icons**: `{'Enabled ✨' if directives.get('floating_icons') else 'Standard'}`\n"
        f"• **Text Alignment/Position**: `{directives.get('text_position', 'bottom')} | {directives.get('text_align', 'center')}`"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reset_user_session(chat_id)
    await update.message.reply_text("Session reset. Buffered photos and active topic cleared from memory.")

async def process_carousel_job(
    chat_id: int,
    user_images: list,
    heading: str,
    is_3d: bool,
    force_single_photo: bool,
    floating_icons: bool,
    text_position: str,
    text_align: str,
    context: ContextTypes.DEFAULT_TYPE
):
    style_label = "3D Luxury Glass" if is_3d else "Editorial Studio"
    photo_label = "1-Photo Hero Cover" if (force_single_photo or len(user_images) < 4) else "4-Photo 2×2 Combo Grid"
    
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ *Preparing {photo_label} with {style_label}...*\nHeading: `{heading}`",
        parse_mode="Markdown"
    )
    
    work_dir = tempfile.mkdtemp(prefix="ron_carousel_")
    
    try:
        # Guarantee disk-backed input images
        saved_images = []
        for i, img_item in enumerate(user_images):
            img_path = os.path.join(work_dir, f"input_{i+1}.jpg")
            if isinstance(img_item, (bytes, bytearray)):
                with open(img_path, "wb") as f:
                    f.write(img_item)
            elif isinstance(img_item, str) and os.path.exists(img_item):
                shutil.copyfile(img_item, img_path)
            saved_images.append(img_path)
            
        if force_single_photo and len(saved_images) > 1:
            saved_images = saved_images[:1]
            
        loop = asyncio.get_event_loop()
        guidelines_str = get_user_guidelines_str(chat_id)
        
        custom_script = get_custom_script(chat_id)
        if custom_script:
            content_data = custom_script
            clear_custom_script(chat_id)
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"✍️ *Synthesizing researched 5-slide copy...*\nHeading: `{heading}`",
                parse_mode="Markdown"
            )
            content_data = await loop.run_in_executor(
                None,
                generate_carousel_content,
                heading,
                saved_images,
                guidelines_str
            )
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🎨 *Rendering 1080×1350 canvas with Playwright (Face-Safe Framing)...*",
            parse_mode="Markdown"
        )
        
        png_slides = await render_carousel_slides(
            content_data=content_data,
            image_paths=saved_images,
            work_dir=work_dir,
            is_3d=is_3d,
            special_edit="",
            force_single_photo=force_single_photo,
            floating_icons=floating_icons,
            text_position=text_position,
            text_align=text_align
        )
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🚀 *Uploading high-resolution carousel album...*",
            parse_mode="Markdown"
        )
        
        # 1. Instagram Photo Preview Album
        media_group = []
        for i, slide_path in enumerate(png_slides):
            caption = f"Slide {i+1} of 5" if i == 0 else None
            with open(slide_path, "rb") as f:
                media_group.append(InputMediaPhoto(f.read(), caption=caption))
        await context.bot.send_media_group(chat_id=chat_id, media=media_group, write_timeout=120.0, read_timeout=120.0)
        
        # 2. Uncompressed PNG Documents for lossless publishing
        doc_group = []
        for i, slide_path in enumerate(png_slides):
            with open(slide_path, "rb") as f:
                doc_group.append(InputMediaDocument(f.read(), filename=f"slide_{i+1}.png"))
        await context.bot.send_media_group(chat_id=chat_id, media=doc_group, write_timeout=120.0, read_timeout=120.0)
        
        # Clear pending buffer after successful production
        clear_pending_photos(chat_id)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ **Carousel rendered successfully.** All 5 slides delivered above.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Render pipeline error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Pipeline notice: {str(e)}"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    
    photo = msg.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = await photo_file.download_as_bytearray()
    
    caption = (msg.caption or "").strip()
    caption_lower = caption.lower()
    
    # 1. Save Asset Tag shortcut
    if "#save" in caption_lower or "save as" in caption_lower or caption_lower.startswith("save "):
        parts = caption.replace("#save", "").replace("save as", "").replace("save", "").strip().split()
        if parts:
            save_tag = parts[0]
            saved_name = save_user_asset(chat_id, save_tag, photo_bytes)
            await msg.reply_text(f"Asset registered as `@{saved_name}`. Available for future compositions.")
            return

    # Buffer photo to persistent disk
    save_pending_photo(chat_id, bytes(photo_bytes))
    
    media_group_id = msg.media_group_id
    if media_group_id:
        if media_group_id not in USER_MEDIA_GROUPS:
            USER_MEDIA_GROUPS[media_group_id] = {
                "caption": caption,
                "chat_id": chat_id
            }
            # Give time for all media group photos to arrive
            await asyncio.sleep(2.0)
            group_data = USER_MEDIA_GROUPS.pop(media_group_id, None)
            final_caption = group_data.get("caption") if group_data else caption
            
            pending = get_pending_photos(chat_id)
            if final_caption:
                await handle_incoming_instruction_or_render(update, context, chat_id, final_caption, pending)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Received album ({len(pending)} photos buffered). What topic should we create?"
                )
        else:
            if caption:
                USER_MEDIA_GROUPS[media_group_id]["caption"] = caption
    else:
        pending = get_pending_photos(chat_id)
        if caption:
            await handle_incoming_instruction_or_render(update, context, chat_id, caption, pending)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Photo buffered (Total: {len(pending)}). Drop a topic or say *'banao'* to produce."
            )

async def handle_incoming_instruction_or_render(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    pending_photos: list
):
    ctx = {
        "photos_count": len(pending_photos),
        "active_heading": get_active_heading(chat_id),
        "is_3d": get_3d_mode(chat_id)
    }
    
    analysis = await asyncio.get_event_loop().run_in_executor(
        None, analyze_user_message, chat_id, text, ctx
    )
    
    wants_render = analysis.get("wants_render", False)
    intent = analysis.get("intent", "CHAT")
    reply = analysis.get("reply", "Understood.")
    resolved_head = analysis.get("resolved_heading") or get_active_heading(chat_id)
    
    directives = analysis.get("visual_directives", {})
    photo_req = analysis.get("photo_count_requested")
    force_single = (photo_req == 1) or (directives.get("photo_count") == 1)
    
    is_3d = (analysis.get("style_mode") == "3D") or get_3d_mode(chat_id)
    floating_icons = directives.get("floating_icons", False)
    text_pos = directives.get("text_position", "bottom")
    text_align = directives.get("text_align", "center")
    
    # If user says conversational prompt like "bro" / "bhai" / "banao" and we have photos & topic/script in memory
    lower_input = text.strip().lower()
    if lower_input in ["bro", "bhai", "banao", "make", "chalo", "render", "kya hua", "yo"]:
        if len(pending_photos) > 0 and (get_active_heading(chat_id) or get_custom_script(chat_id)):
            wants_render = True

    if wants_render or intent == "RENDER":
        if len(pending_photos) == 0:
            await update.message.reply_text(
                f"{reply}\n\n⚠️ *Photos buffered nahi hain.* Kripya 1 ya 4 photos bhejein ya saved tag (`@tag`) mention karein."
            )
            return
            
        final_heading = resolved_head or "Being a daughter of a mutual fund distributor, I know one thing…"
        await update.message.reply_text(reply)
        
        chosen_photos = pending_photos
        if force_single and len(chosen_photos) > 1:
            chosen_photos = [chosen_photos[0]]
            
        await process_carousel_job(
            chat_id=chat_id,
            user_images=chosen_photos,
            heading=final_heading,
            is_3d=is_3d,
            force_single_photo=force_single,
            floating_icons=floating_icons,
            text_position=text_pos,
            text_align=text_align,
            context=context
        )
    elif intent == "SET_INSTRUCTION":
        await update.message.reply_text(reply)
    elif intent == "SET_TOPIC":
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(reply)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat_id
    raw_text = msg.text.strip()
    lower_text = raw_text.lower()
    
    # 1. Quick Code Shortcuts
    if lower_text in ["111reset", "/clear", "#clear", "clear", "reset"]:
        await clear_command(update, context)
        return
        
    if lower_text in ["000status", "/status", "#status", "status"]:
        await status_command(update, context)
        return
        
    if lower_text in ["/assets", "#assets", "assets"]:
        tags = list_user_assets(chat_id)
        tags_str = ", ".join([f"`@{t}`" for t in tags]) if tags else "None"
        await update.message.reply_text(f"Saved memory assets: {tags_str}")
        return

    # Instruction Code: 987inst
    if lower_text.startswith("987inst") or lower_text.startswith(("#inst", "/inst")):
        inst_text = raw_text.replace("987inst", "").replace("#inst", "").replace("/inst", "").strip()
        update_user_guidelines(chat_id, inst_text)
        await update.message.reply_text(f"Guideline locked: `{inst_text}`.")
        return

    # Heading Code: 456head
    if lower_text.startswith("456head") or lower_text.startswith(("#heading", "/heading")):
        head_text = raw_text.replace("456head", "").replace("#heading", "").replace("/heading", "").strip()
        set_active_heading(chat_id, head_text)
        await update.message.reply_text(f"Heading locked: `{head_text}`.")
        return

    # Style Code: 789style
    if lower_text.startswith("789style") or lower_text in ["#3d", "3d mode", "789style 3d"]:
        if "3d" in lower_text:
            set_3d_mode(chat_id, True)
            await update.message.reply_text("3D Luxury Elements mode activated.")
        else:
            set_3d_mode(chat_id, False)
            await update.message.reply_text("Standard clean studio mode active.")
        return

    # Resolve @tags from text and buffer them
    resolved_paths = resolve_assets_from_text(chat_id, raw_text)
    if resolved_paths:
        for p in resolved_paths:
            with open(p, "rb") as f:
                save_pending_photo(chat_id, f.read())

    # Fast-path 312make code trigger
    is_312make = lower_text.startswith("312make") or lower_text.startswith(("#make", "/make"))
    if is_312make:
        pending = get_pending_photos(chat_id)
        if len(pending) == 0:
            await update.message.reply_text("No photos buffered. Please upload photos or tag saved assets (e.g. `@bank`).")
            return
            
        is_3d = ("#3d" in lower_text) or ("3d" in lower_text) or get_3d_mode(chat_id)
        heading = raw_text
        for prefix in ["312make", "#make", "/make", "#3d"]:
            heading = heading.replace(prefix, "")
        heading = heading.strip() or get_active_heading(chat_id) or "Being a daughter of a mutual fund distributor, I know one thing…"
        
        force_single = ("1 photo" in lower_text) or (len(pending) < 4)
        floating_icons = ("floating" in lower_text) or is_3d
        
        await process_carousel_job(
            chat_id=chat_id,
            user_images=pending,
            heading=heading,
            is_3d=is_3d,
            force_single_photo=force_single,
            floating_icons=floating_icons,
            text_position="bottom",
            text_align="center",
            context=context
        )
        return

    # Master comprehension engine for natural language
    pending = get_pending_photos(chat_id)
    await handle_incoming_instruction_or_render(update, context, chat_id, raw_text, pending)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment!")
        
    t_request = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=30.0,
        read_timeout=120.0,
        write_timeout=120.0
    )
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(t_request).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info("Ron Executive Carousel Agent is live on Telegram! Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
