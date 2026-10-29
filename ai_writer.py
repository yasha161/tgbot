import os
import json
import base64
import requests
from dotenv import load_dotenv
from json_repair import repair_json

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "c6e9f428b957aecbe87557c7153155c0")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_AI_GATEWAY_URL = os.getenv("CLOUDFLARE_AI_GATEWAY_URL")

def get_gemini_endpoint(model: str = "gemini-2.5-flash", action: str = "generateContent") -> str:
    if CLOUDFLARE_AI_GATEWAY_URL:
        base = CLOUDFLARE_AI_GATEWAY_URL.rstrip("/")
        return f"{base}/v1beta/models/{model}:{action}?key={GEMINI_API_KEY}"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}?key={GEMINI_API_KEY}"

def call_cloudflare_workers_ai(prompt: str, system_prompt: str = "") -> str:
    if not CLOUDFLARE_API_TOKEN:
        raise ValueError("Cloudflare API token not configured")
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-70b-instruct"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    resp = requests.post(url, headers=headers, json={"messages": messages}, timeout=25)
    if resp.status_code == 200:
        res_data = resp.json().get("result", {})
        return res_data.get("response", "")
    else:
        raise RuntimeError(f"Cloudflare Workers AI error ({resp.status_code}): {resp.text}")

INTELLIGENCE_SYSTEM_PROMPT = """
You are Ron, an executive-level creative technologist and Instagram Carousel art director.
You speak with professional competence, calm clarity, and concise confidence in natural English/Hinglish.
Avoid informal fluff, repetitive intros, or cringe phrases. Keep your answers direct, sharp, and helpful.

Your capabilities:
1. Conversation Memory: If the user refers to previous messages (e.g. "purani chat padho", "upar jo bataya tha wahi use karo", "read previous context"), analyze the full conversation history to extract their intended topic and guidelines.
2. Intent Classification:
   - "CHAT": Discussing concepts, giving feedback, or general questions.
   - "INSTRUCTION": Setting aesthetic or editorial rules (e.g. "text 1-2 lines only", "cover stomach/midriff area", "use yellow headline").
   - "TRIGGER_MAKE": Starting the carousel render (e.g. "312make", "bana do", "shuru karo", "make it", or referring to previous chat to render).

Return strictly JSON with this schema:
{
  "intent": "CHAT" | "INSTRUCTION" | "TRIGGER_MAKE",
  "reply": "Professional, concise response confirming the action or answering the query",
  "extracted_instruction": "Clean instruction to save, or null if none",
  "extracted_heading": "The exact heading/topic synthesized from current or previous chat, or null"
}
"""

CAROUSEL_SYSTEM_PROMPT = """
You are a senior Instagram Carousel strategist specializing in high-retention wealth, finance, and personal growth content.

Strict Production Rules:
1. Heading Fidelity: Slide 1 cover must use the user's exact heading verbatim as the primary hook. Break into 2 balanced lines.
2. Concise Body Copy: Inside slides (Slides 2-4) must have exactly 1 to 2 lines of high-impact text (max 3 lines in exceptional cases). Zero filler.
3. Bold Keywords: Wrap key numbers, stats, and power terms in <b>bold tags</b>.
4. Schema Strictness: Output must strictly match this JSON format:
{
  "slide1": {
    "headline": "Line 1 of heading",
    "highlight": "Line 2 of heading"
  },
  "slide2": {
    "title": "#1 – [Punchy Truth / Reality Hook]",
    "lines": [
      "Line 1 with <b>bold emphasis</b>.",
      "Line 2 takeaway."
    ]
  },
  "slide3": {
    "title": "#2 – [Tangible Comparison / Math]",
    "lines": [
      "Concrete numbers with <b>bold figures</b>.",
      "Direct comparison."
    ]
  },
  "slide4": {
    "title": "#3 – [Discipline / Mindset Rule]",
    "lines": [
      "Core rule with <b>bold takeaway</b>.",
      "Actionable truth."
    ]
  },
  "slide5": {
    "title": "Start early. Stay consistent. Let it compound.",
    "lines": [
      "The best time was <b>10 years ago</b>. The next best time is <b>today</b>.",
      "Save this post & share it with someone who needs to see this. 💡"
    ],
    "cta": "SAVE & SHARE FOR LATER 📌"
  }
}
"""

USER_CONVERSATIONS = {}

def safe_parse_json(raw_text: str) -> dict:
    """
    Bulletproof JSON parser using json-repair.
    Never crashes on unescaped newlines, missing quotes, or truncated tokens.
    """
    try:
        parsed = repair_json(raw_text, return_objects=True)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
            return parsed[0]
    except Exception as e:
        print(f"repair_json error: {e}")
        
    # Manual fallback regex
    import re
    m = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

def analyze_user_message(user_id: int, user_message: str, current_context: dict) -> dict:
    url = get_gemini_endpoint("gemini-2.5-flash", "generateContent")
    
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []
    history = USER_CONVERSATIONS[user_id]
    
    # Context summary injected
    recent_history_text = "\n".join([f"{t['role'].upper()}: {t['parts'][0]['text']}" for t in history[-8:]])
    context_note = f"\n[Context:\nPhotos in buffer: {current_context.get('photos_count', 0)}\nActive Heading: {current_context.get('active_heading')}\nActive Instructions: {current_context.get('instructions')}\nRecent Chat Log:\n{recent_history_text}\n]"
    
    contents = [
        {"role": "user", "parts": [{"text": INTELLIGENCE_SYSTEM_PROMPT + context_note}]},
        {"role": "model", "parts": [{"text": "Understood. I will parse all incoming user messages with professional precision, context memory, and structured JSON output."}]}
    ] + history[-6:] + [
        {"role": "user", "parts": [{"text": user_message}]}
    ]
    
    payload = {
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    # Try Gemini 2.5 Flash
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = safe_parse_json(raw_text)
            if parsed and "intent" in parsed:
                history.append({"role": "user", "parts": [{"text": user_message}]})
                history.append({"role": "model", "parts": [{"text": parsed.get("reply", "")}]})
                return parsed
    except Exception as e:
        print(f"Gemini analysis error: {e}")
        
    # Cloudflare Workers AI Fallback
    try:
        cf_raw = call_cloudflare_workers_ai(
            f"{context_note}\n\nUser Message: {user_message}\nReturn valid JSON with intent, reply, extracted_instruction, extracted_heading.",
            INTELLIGENCE_SYSTEM_PROMPT
        )
        parsed = safe_parse_json(cf_raw)
        if parsed and "intent" in parsed:
            history.append({"role": "user", "parts": [{"text": user_message}]})
            history.append({"role": "model", "parts": [{"text": parsed.get("reply", "")}]})
            return parsed
    except Exception as e2:
        print(f"Cloudflare fallback error: {e2}")
        
    return {
        "intent": "CHAT",
        "reply": "Understood. Let me know your topic or use `312make` to render.",
        "extracted_instruction": None,
        "extracted_heading": None
    }

def ensure_slide_keys(data: dict, fallback_heading: str) -> dict:
    """
    Guarantees that all 5 slide keys exist and have proper structure.
    """
    default_structure = {
        "slide1": {
            "headline": fallback_heading,
            "highlight": "here is what you need to know:"
        },
        "slide2": {
            "title": "#1 – Your bank balance is NOT your wealth.",
            "lines": [
                "Savings accounts earn <b>~3% interest</b>, while inflation eats <b>6% to 7%</b>.",
                "Idle cash silently loses <b>real purchasing power</b> every single year."
            ]
        },
        "slide3": {
            "title": "#2 – Saving protects, investing multiplies.",
            "lines": [
                "Saving <b>₹10,000/mo</b> gives you ₹12 Lakhs in 10 years.",
                "Invested at 12% in mutual funds, it becomes <b>~₹23.2 Lakhs</b>."
            ]
        },
        "slide4": {
            "title": "#3 – Consistency beats market timing.",
            "lines": [
                "You do not need a lump sum or market expertise to start.",
                "A monthly SIP removes emotion and <b>averages out volatility</b>."
            ]
        },
        "slide5": {
            "title": "Start early. Stay consistent. Let it compound.",
            "lines": [
                "The best time to start was <b>10 years ago</b>.",
                "The second best time is <b>right now</b>."
            ],
            "cta": "SAVE & SHARE FOR LATER 📌"
        }
    }
    
    if not isinstance(data, dict):
        return default_structure
        
    for key in ["slide1", "slide2", "slide3", "slide4", "slide5"]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = default_structure[key]
            
    # Validate slide1
    if "headline" not in data["slide1"]:
        data["slide1"]["headline"] = fallback_heading
    if "highlight" not in data["slide1"]:
        data["slide1"]["highlight"] = "here is what you need to know:"
        
    # Validate slides 2 to 5
    for k in ["slide2", "slide3", "slide4", "slide5"]:
        if "title" not in data[k]:
            data[k]["title"] = default_structure[k]["title"]
        if "lines" not in data[k] or not isinstance(data[k]["lines"], list) or len(data[k]["lines"]) == 0:
            data[k]["lines"] = default_structure[k]["lines"]
            
    return data

def generate_carousel_content(user_heading: str, image_paths: list = None, custom_instructions: str = "") -> dict:
    url = get_gemini_endpoint("gemini-2.5-flash", "generateContent")
    
    parts = []
    if image_paths and len(image_paths) > 0 and os.path.exists(image_paths[0]):
        try:
            with open(image_paths[0], "rb") as img_f:
                b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                mime_type = "image/jpeg" if image_paths[0].lower().endswith((".jpg", ".jpeg")) else "image/png"
                parts.append({
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": b64_data
                    }
                })
        except Exception as e:
            print(f"Image load warning: {e}")
            
    prompt_text = f"{CAROUSEL_SYSTEM_PROMPT}\n\nExact User Heading: {user_heading}"
    if custom_instructions:
        prompt_text += f"\n\nActive Custom Guidelines:\n{custom_instructions}"
        
    parts.append({"text": prompt_text})
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    # 1. Primary: Gemini 2.5 Flash
    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = safe_parse_json(raw_text)
            if parsed and "slide1" in parsed:
                return ensure_slide_keys(parsed, user_heading)
    except Exception as e:
        print(f"Gemini generation error: {e}")
        
    # 2. Secondary: Cloudflare Workers AI
    try:
        cf_raw = call_cloudflare_workers_ai(
            prompt_text + "\n\nOutput strictly valid JSON with keys: slide1, slide2, slide3, slide4, slide5.",
            CAROUSEL_SYSTEM_PROMPT
        )
        parsed = safe_parse_json(cf_raw)
        if parsed and "slide1" in parsed:
            return ensure_slide_keys(parsed, user_heading)
    except Exception as e2:
        print(f"Cloudflare generation fallback error: {e2}")
        
    # 3. Fail-safe guaranteed default
    return ensure_slide_keys({}, user_heading)
