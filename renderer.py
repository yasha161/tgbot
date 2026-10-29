import os
import cv2
import numpy as np
from PIL import Image, ImageEnhance
from playwright.async_api import async_playwright

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def enhance_studio_quality(pil_img: Image.Image, special_edit: str = "") -> Image.Image:
    """
    Applies studio-grade contrast, sharpness, and rich color grading.
    """
    contrast_mult = 1.15 if "high_contrast" in special_edit else 1.12
    sharpness_mult = 1.30 if "sharp" in special_edit else 1.22
    color_mult = 1.12 if "vibrant" in special_edit else 1.10
    
    img = ImageEnhance.Contrast(pil_img).enhance(contrast_mult)
    img = ImageEnhance.Sharpness(img).enhance(sharpness_mult)
    img = ImageEnhance.Color(img).enhance(color_mult)
    img = ImageEnhance.Brightness(img).enhance(1.02)
    return img

def detect_face_box(pil_img: Image.Image):
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        if len(faces) == 0:
            return None
        min_x = min(f[0] for f in faces)
        min_y = min(f[1] for f in faces)
        max_x = max(f[0] + f[2] for f in faces)
        max_y = max(f[1] + f[3] for f in faces)
        return (min_x + (max_x - min_x) // 2, min_y + (max_y - min_y) // 2, max_x - min_x, max_y - min_y)
    except Exception as e:
        print(f"Face detect error: {e}")
        return None

def smart_face_crop(img_path: str, target_w: int, target_h: int, face_position: str = "top", special_edit: str = "") -> Image.Image:
    orig_img = Image.open(img_path).convert("RGB")
    enhanced = enhance_studio_quality(orig_img, special_edit)
    w, h = enhanced.size
    target_aspect = target_w / target_h # 0.8
    
    face = detect_face_box(enhanced)
    
    if face:
        cx, cy, fw, fh = face
        ideal_crop_h = int(fh * 4.8)
        crop_h = max(int(h * 0.7), min(h, ideal_crop_h))
        crop_w = int(crop_h * target_aspect)
        
        if crop_w > w:
            crop_w = w
            crop_h = int(w / target_aspect)
            
        if face_position == "top":
            crop_top = max(0, int(cy - crop_h * 0.26))
            crop_bottom = crop_top + crop_h
            if crop_bottom > h:
                crop_bottom = h
                crop_top = max(0, crop_bottom - crop_h)
        elif face_position == "bottom":
            crop_top = max(0, int(cy - crop_h * 0.65))
            crop_bottom = crop_top + crop_h
            if crop_bottom > h:
                crop_bottom = h
                crop_top = max(0, crop_bottom - crop_h)
        else:
            crop_top = max(0, int(cy - crop_h / 2))
            crop_bottom = crop_top + crop_h
            if crop_bottom > h:
                crop_bottom = h
                crop_top = max(0, crop_bottom - crop_h)
                
        crop_left = max(0, int(cx - crop_w / 2))
        crop_right = crop_left + crop_w
        if crop_right > w:
            crop_right = w
            crop_left = max(0, crop_right - crop_w)
            
        cropped = enhanced.crop((crop_left, crop_top, crop_right, crop_bottom))
    else:
        current_aspect = w / h
        if current_aspect < target_aspect:
            crop_h = int(w / target_aspect)
            y_offset = 0 if face_position == "top" else int((h - crop_h) * 0.35)
            cropped = enhanced.crop((0, y_offset, w, y_offset + crop_h))
        else:
            crop_w = int(h * target_aspect)
            x_offset = int((w - crop_w) / 2)
            cropped = enhanced.crop((x_offset, 0, x_offset + crop_w, h))
            
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

def build_slide1_combo_html(q_paths, headline, highlight, is_3d: bool = False, floating_icons: bool = False, text_position: str = "bottom", text_align: str = "center"):
    q_urls = [f"file:///{p.replace(os.sep, '/')}" for p in q_paths]
    headline_clean = headline.replace("\n", "<br>")
    
    shadow_style = "0 8px 32px rgba(255, 222, 67, 0.4), 0 4px 20px rgba(0,0,0,0.98)" if is_3d else "0 4px 24px rgba(0,0,0,0.98), 0 2px 6px rgba(0,0,0,0.95)"
    badge_style = "box-shadow: 0 0 25px rgba(255, 222, 67, 0.45); transform: perspective(800px) rotateX(4deg);" if is_3d else ""
    
    floating_icon_html = ""
    if floating_icons:
        floating_icon_html = """
        <div style="position: absolute; top: 38px; left: 50%; transform: translateX(-50%); z-index: 20;
                    background: rgba(10, 16, 26, 0.85); backdrop-filter: blur(14px);
                    border: 1.5px solid rgba(255, 222, 67, 0.6); border-radius: 9999px;
                    padding: 8px 24px; color: #FFDE43; font-size: 14px; font-weight: 800;
                    letter-spacing: 2px; text-transform: uppercase;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.8), 0 0 20px rgba(255, 222, 67, 0.35);">
            💎 4-PART WEALTH PLAYBOOK
        </div>
        """
        
    align_style = "text-align: left; align-items: flex-start; padding-left: 55px;" if text_align == "left" else "text-align: center; align-items: center;"
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            width: 1080px; height: 1350px; overflow: hidden; position: relative;
            background-color: #06090F; font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .grid-container {{
            position: absolute; inset: 0; display: grid;
            grid-template-columns: 539px 539px; grid-template-rows: 674px 674px; gap: 2px;
            background-color: #000; z-index: 1;
        }}
        .quadrant {{ width: 100%; height: 100%; background-size: cover; background-position: center; }}
        .q1 {{ background-image: url('{q_urls[0]}'); }}
        .q2 {{ background-image: url('{q_urls[1] if len(q_urls) > 1 else q_urls[0]}'); }}
        .q3 {{ background-image: url('{q_urls[2] if len(q_urls) > 2 else q_urls[0]}'); }}
        .q4 {{ background-image: url('{q_urls[3] if len(q_urls) > 3 else q_urls[0]}'); }}
        .center-band {{
            position: absolute; top: 50%; left: 0; right: 0; transform: translateY(-50%);
            height: 340px;
            background: linear-gradient(to bottom, rgba(5,8,14,0) 0%, rgba(5,8,14,0.78) 18%, rgba(5,8,14,0.94) 50%, rgba(5,8,14,0.78) 82%, rgba(5,8,14,0) 100%);
            z-index: 10; display: flex; flex-direction: column; justify-content: center;
            padding: 0 40px; {align_style}
        }}
        .cover-headline {{
            color: #FFDE43; font-size: 52px; font-weight: 800; line-height: 1.25;
            text-shadow: {shadow_style};
        }}
        .cover-headline span {{ color: #FFFFFF; }}
        .bottom-bar {{
            position: absolute; bottom: 35px; left: 0; right: 0; display: flex; justify-content: center; z-index: 10;
        }}
        .swipe-badge {{
            font-size: 14px; font-weight: 800; letter-spacing: 2px; color: #FFFFFF;
            background: rgba(0,0,0,0.65); border: 1px solid rgba(255,255,255,0.25);
            padding: 8px 22px; border-radius: 9999px; text-transform: uppercase;
            {badge_style}
        }}
    </style>
</head>
<body>
    {floating_icon_html}
    <div class="grid-container">
        <div class="quadrant q1"></div><div class="quadrant q2"></div>
        <div class="quadrant q3"></div><div class="quadrant q4"></div>
    </div>
    <div class="center-band">
        <h1 class="cover-headline">{headline_clean}<br><span>{highlight}</span></h1>
    </div>
    <div class="bottom-bar">
        <div class="swipe-badge">SWIPE TO READ ➔</div>
    </div>
</body>
</html>"""

def build_single_photo_cover_html(bg_path, headline, highlight, is_3d: bool = False, floating_icons: bool = False, text_position: str = "bottom", text_align: str = "center"):
    bg_url = f"file:///{bg_path.replace(os.sep, '/')}"
    headline_clean = headline.replace("\n", "<br>")
    
    shadow_style = "0 8px 35px rgba(255, 222, 67, 0.45), 0 4px 20px rgba(0,0,0,0.98)" if is_3d else "0 4px 20px rgba(0,0,0,0.95), 0 2px 4px rgba(0,0,0,0.9)"
    tag_style = "box-shadow: 0 10px 30px rgba(255, 222, 67, 0.35); transform: perspective(800px) rotateX(4deg);" if is_3d else ""
    
    floating_icon_badge = "💎 REAL WEALTH WISDOM" if not floating_icons else "📈 PRO RESEARCH BREAKDOWN"
    
    # Text position and scrim configuration
    if text_position == "center":
        scrim_css = """
            position: absolute; inset: 0;
            background: radial-gradient(circle at center, rgba(5,8,14,0.90) 0%, rgba(5,8,14,0.75) 55%, rgba(5,8,14,0.35) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "top: 50%; transform: translateY(-50%); bottom: auto;"
    elif text_position == "top":
        scrim_css = """
            position: absolute; top: 0; left: 0; width: 1080px; height: 650px;
            background: linear-gradient(to bottom, rgba(5,8,14,0.99) 0%, rgba(5,8,14,0.92) 50%, rgba(5,8,14,0.55) 80%, rgba(5,8,14,0) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "top: 75px; bottom: auto;"
    else:
        # Default bottom (safely covers midriff and preserves face at top 30%)
        scrim_css = """
            position: absolute; bottom: 0; left: 0; width: 1080px; height: 680px;
            background: linear-gradient(to top, rgba(5,8,14,0.99) 0%, rgba(5,8,14,0.92) 50%, rgba(5,8,14,0.55) 80%, rgba(5,8,14,0) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "bottom: 75px; top: auto;"
        
    align_css = "text-align: left; align-items: flex-start; border-left: 4px solid #FFDE43; padding-left: 24px;" if text_align == "left" else "text-align: center; align-items: center;"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            width: 1080px; height: 1350px; overflow: hidden; position: relative;
            background-color: #06090F; font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .photo-layer {{
            position: absolute; inset: 0; background-image: url('{bg_url}');
            background-size: cover; background-position: center top; z-index: 1;
        }}
        .floating-tag {{
            position: absolute; top: 55px; left: 50%; transform: translateX(-50%);
            z-index: 10; background: rgba(0, 0, 0, 0.65); backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 222, 67, 0.4); border-radius: 9999px;
            padding: 10px 28px; color: #FFDE43; font-size: 15px; font-weight: 800;
            letter-spacing: 2px; text-transform: uppercase;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            {tag_style}
        }}
        .scrim-layer {{
            {scrim_css}
        }}
        .text-container {{
            position: absolute; {container_pos} left: 55px; right: 55px; z-index: 10;
            display: flex; flex-direction: column; gap: 20px;
            {align_css}
        }}
        .cover-headline {{
            color: #FFDE43; font-size: 48px; font-weight: 800; line-height: 1.25;
            letter-spacing: -0.5px; text-shadow: {shadow_style};
            max-width: 960px;
        }}
        .cover-headline span {{ color: #FFFFFF; }}
        .swipe-badge {{
            font-size: 14px; font-weight: 800; letter-spacing: 2px; color: #FFFFFF;
            background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
            padding: 10px 28px; border-radius: 9999px; text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="photo-layer"></div>
    <div class="floating-tag">{floating_icon_badge}</div>
    <div class="scrim-layer"></div>
    <div class="text-container">
        <h1 class="cover-headline">{headline_clean}<br><span>{highlight}</span></h1>
        <div class="swipe-badge">SWIPE TO READ ➔</div>
    </div>
</body>
</html>"""

def build_glass_card_slide_html(bg_path, title, lines, icon="💡", cta=None, is_3d: bool = False, floating_icons: bool = False, text_position: str = "bottom", text_align: str = "center"):
    bg_url = f"file:///{bg_path.replace(os.sep, '/')}"
    lines_html = "".join([f'<p class="body-line">{line}</p>' for line in lines])
    cta_html = f'<div class="cta-badge">{cta}</div>' if cta else ""
    
    card_3d_style = ""
    if is_3d or floating_icons:
        card_3d_style = """
            transform: perspective(1000px) rotateX(3deg);
            box-shadow: 0 20px 50px rgba(0,0,0,0.85), 0 0 35px rgba(255, 222, 67, 0.35);
            border: 1.5px solid rgba(255, 222, 67, 0.6) !important;
        """
        
    # Text position and scrim configuration
    if text_position == "center":
        scrim_css = """
            position: absolute; inset: 0;
            background: radial-gradient(circle at center, rgba(5,8,14,0.92) 0%, rgba(5,8,14,0.78) 60%, rgba(5,8,14,0.40) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "top: 50%; transform: translateY(-50%); bottom: auto;"
    elif text_position == "top":
        scrim_css = """
            position: absolute; top: 0; left: 0; width: 1080px; height: 650px;
            background: linear-gradient(to bottom, rgba(5,8,14,0.99) 0%, rgba(5,8,14,0.90) 50%, rgba(5,8,14,0.55) 78%, rgba(5,8,14,0) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "top: 75px; bottom: auto;"
    else:
        scrim_css = """
            position: absolute; bottom: 0; left: 0; width: 1080px; height: 650px;
            background: linear-gradient(to top, rgba(5,8,14,0.99) 0%, rgba(5,8,14,0.90) 50%, rgba(5,8,14,0.55) 78%, rgba(5,8,14,0) 100%);
            z-index: 5; pointer-events: none;
        """
        container_pos = "bottom: 75px; top: auto;"
        
    align_css = "text-align: left; align-items: flex-start; border-left: 4px solid #FFDE43; padding-left: 24px;" if text_align == "left" else "text-align: center; align-items: center;"
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            width: 1080px; height: 1350px; overflow: hidden; position: relative;
            background-color: #06090F; font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .photo-layer {{
            position: absolute; inset: 0; background-image: url('{bg_url}');
            background-size: cover; background-position: center top; z-index: 1;
        }}
        .scrim-layer {{
            {scrim_css}
        }}
        .floating-pill {{
            display: inline-flex; align-items: center; gap: 8px;
            background: rgba(255, 222, 67, 0.15); border: 1.5px solid rgba(255, 222, 67, 0.4);
            border-radius: 9999px; padding: 6px 20px; color: #FFDE43;
            font-size: 14px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;
            {card_3d_style}
        }}
        .text-container {{
            position: absolute; {container_pos} left: 55px; right: 55px; z-index: 10;
            display: flex; flex-direction: column; gap: 16px;
            {align_css}
        }}
        .headline {{
            color: #FFDE43; font-size: 44px; font-weight: 800; line-height: 1.25;
            letter-spacing: -0.5px; text-shadow: 0 4px 20px rgba(0,0,0,0.95), 0 2px 4px rgba(0,0,0,0.9);
            max-width: 960px;
        }}
        .body-stack {{ display: flex; flex-direction: column; gap: 12px; max-width: 940px; }}
        .body-line {{
            color: #FFFFFF; font-family: 'Inter', sans-serif; font-size: 27px; font-weight: 400;
            line-height: 1.45; text-shadow: 0 2px 10px rgba(0,0,0,0.95);
        }}
        .body-line b {{ font-weight: 700; color: #FFFFFF; }}
        .cta-badge {{
            margin-top: 6px; font-size: 15px; font-weight: 800; letter-spacing: 2px;
            color: #06090F; background: #FFDE43; padding: 12px 32px; border-radius: 9999px;
            text-transform: uppercase; box-shadow: 0 4px 18px rgba(255,222,67,0.35);
        }}
    </style>
</head>
<body>
    <div class="photo-layer"></div>
    <div class="scrim-layer"></div>
    <div class="text-container">
        <div class="floating-pill">{icon} INSIGHT</div>
        <h2 class="headline">{title}</h2>
        <div class="body-stack">{lines_html}</div>
        {cta_html}
    </div>
</body>
</html>"""

async def render_carousel_slides(
    content_data: dict,
    image_paths: list,
    work_dir: str,
    is_3d: bool = False,
    special_edit: str = "",
    force_single_photo: bool = False,
    floating_icons: bool = False,
    text_position: str = "bottom",
    text_align: str = "center"
) -> list:
    os.makedirs(work_dir, exist_ok=True)
    html_files = []
    
    # 1. Slide 1 Cover selection
    use_combo = (len(image_paths) >= 4) and not force_single_photo
    
    if use_combo:
        q_paths = []
        positions = ["top", "top", "bottom", "bottom"]
        for i in range(4):
            q_img = smart_face_crop(image_paths[i], 540, 675, positions[i], special_edit)
            q_out = os.path.join(work_dir, f"q{i+1}.jpg")
            q_img.save(q_out, quality=95)
            q_paths.append(q_out)
        s1_html = build_slide1_combo_html(
            q_paths,
            content_data["slide1"]["headline"],
            content_data["slide1"]["highlight"],
            is_3d,
            floating_icons,
            text_position,
            text_align
        )
    else:
        # Single photo hero cover (Face in top 30%, scrim + text covering stomach)
        s1_img = smart_face_crop(image_paths[0], 1080, 1350, "top", special_edit)
        s1_bg = os.path.join(work_dir, "bg_s1.jpg")
        s1_img.save(s1_bg, quality=95)
        s1_html = build_single_photo_cover_html(
            s1_bg,
            content_data["slide1"]["headline"],
            content_data["slide1"]["highlight"],
            is_3d,
            floating_icons,
            text_position,
            text_align
        )
        
    s1_path = os.path.join(work_dir, "slide_1.html")
    with open(s1_path, "w", encoding="utf-8") as f:
        f.write(s1_html)
    html_files.append((s1_path, os.path.join(work_dir, "slide_1.png")))
    
    # 2. Inside Slides 2 to 5 with floating icons & styling
    icons = ["⚡", "📈", "🛡️", "🚀"] if not is_3d else ["💎", "📈", "🛡️", "🔥"]
    for s_idx, key in enumerate(["slide2", "slide3", "slide4", "slide5"]):
        slide_num = s_idx + 2
        img_src = image_paths[(s_idx + 1) % len(image_paths)]
        
        s_img = smart_face_crop(img_src, 1080, 1350, "top", special_edit)
        bg_out = os.path.join(work_dir, f"bg_s{slide_num}.jpg")
        s_img.save(bg_out, quality=95)
        
        s_data = content_data[key]
        cta = s_data.get("cta") if key == "slide5" else None
        icon = icons[s_idx % len(icons)]
        s_html = build_glass_card_slide_html(
            bg_out,
            s_data["title"],
            s_data["lines"],
            icon,
            cta,
            is_3d,
            floating_icons,
            text_position,
            text_align
        )
        
        s_path = os.path.join(work_dir, f"slide_{slide_num}.html")
        with open(s_path, "w", encoding="utf-8") as f:
            f.write(s_html)
        html_files.append((s_path, os.path.join(work_dir, f"slide_{slide_num}.png")))
        
    # 3. Render all 5 slides with Playwright
    png_outputs = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome")
        except Exception:
            browser = await p.chromium.launch()
            
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        
        for html_file, png_file in html_files:
            file_url = f"file:///{html_file.replace(os.sep, '/')}"
            await page.goto(file_url, wait_until="networkidle")
            await page.wait_for_timeout(600)
            await page.screenshot(path=png_file)
            png_outputs.append(png_file)
            
        await browser.close()
        
    return png_outputs
