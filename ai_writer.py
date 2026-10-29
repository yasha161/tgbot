import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Cloudflare Workers AI & AI Gateway Credentials
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "c6e9f428b957aecbe87557c7153155c0")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_AI_GATEWAY_URL = os.getenv("CLOUDFLARE_AI_GATEWAY_URL")

def get_gemini_endpoint(model: str = "gemini-2.5-flash", action: str = "generateContent") -> str:
    if CLOUDFLARE_AI_GATEWAY_URL:
        base = CLOUDFLARE_AI_GATEWAY_URL.rstrip("/")
        return f"{base}/v1beta/models/{model}:{action}?key={GEMINI_API_KEY}"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}?key={GEMINI_API_KEY}"

def call_cloudflare_workers_ai(prompt: str, system_prompt: str = "") -> str:
    """
    Direct Cloudflare Workers AI edge fallback using Llama 3.1 70B.
    Runs globally across 300+ data centers with 0 billing.
    """
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
        raise RuntimeError(f"Cloudflare Workers AI failed ({resp.status_code}): {resp.text}")

INTELLIGENCE_SYSTEM_PROMPT = """
You are Ron, an elite AI creative partner and Instagram Carousel strategist (just like Antigravity).
You talk in warm, smart, witty Hindi/Hinglish (e.g. "Haan bro", "Samajh gaya bilkul", "Ye tagda idea hai", "Ekdum sorted").

Your job is to analyze the user's message and determine the INTENT:
1. "CHAT": The user is just chatting, asking a question, discussing an idea, greeting, or talking.
2. "INSTRUCTION": The user is giving a preference, rule, or guideline (e.g. "text 1 line hi rakhna", "blue tone rakhna", "heading meri hi use karna", "pet cover karna", "987inst...").
3. "TRIGGER_MAKE": The user wants to start making/rendering the carousel NOW (e.g. "312make", "bana do", "make it", "shuru karo", "#make", "#banao", "#render").

Return strictly JSON with this schema:
{
  "intent": "CHAT" | "INSTRUCTION" | "TRIGGER_MAKE",
  "reply": "Warm, natural Hindi/Hinglish response to the user",
  "extracted_instruction": "The clean instruction to save, or null if none",
  "extracted_heading": "The exact heading/topic if mentioned in this message, or null"
}
"""

CAROUSEL_SYSTEM_PROMPT = """
You are an expert Instagram Carousel strategist.
The user will provide a specific topic or exact heading, and optionally any special user instructions.

CRITICAL RULES:
1. Heading Adherence: Slide 1 cover MUST use the user's provided heading/topic verbatim as the core hook. Do NOT invent unrelated headlines. Split it into 2 natural readable lines.
2. Ultra-Crisp Content:
   - Inside slides MUST have only 1 to 2 lines of high-impact copy (in special cases max 3 lines).
   - No long paragraphs or fluff.
   - Use <b>bold tags</b> for key numbers, percentages, or strong power words.
3. Logical Flow:
   - Slide 1: Cover with user's exact heading.
   - Slide 2: Numbered '#1 – ...' counter-intuitive reality or core truth.
   - Slide 3: Numbered '#2 – ...' tangible math or comparison.
   - Slide 4: Numbered '#3 – ...' consistency or mindset rule.
   - Slide 5: Numbered '#4 – ...' or high-impact summary hook + CTA badge.

Return strictly valid JSON with this schema:
{
  "slide1": {
    "headline": "Line 1 of user heading",
    "highlight": "Line 2 of user heading"
  },
  "slide2": {
    "title": "#1 – [Punchy Truth]",
    "lines": [
      "1 to 2 lines max with <b>bold key points</b>.",
      "Clear, impactful takeaway."
    ]
  },
  "slide3": {
    "title": "#2 – [Tangible Comparison]",
    "lines": [
      "Concrete numbers or math with <b>bold emphasis</b>.",
      "Direct comparison."
    ]
  },
  "slide4": {
    "title": "#3 – [Discipline Rule]",
    "lines": [
      "Mindset or consistency wisdom with <b>bold phrases</b>.",
      "Short actionable truth."
    ]
  },
  "slide5": {
    "title": "Start early. Stay consistent. Let it compound.",
    "lines": [
      "The best time was <b>10 years ago</b>. The next best time is <b>now</b>.",
      "Save this post & share it with someone who needs to see this. 💡"
    ],
    "cta": "SAVE & SHARE FOR LATER 📌"
  }
}
"""

USER_CONVERSATIONS = {}

def clean_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

def analyze_user_message(user_id: int, user_message: str, current_context: dict) -> dict:
    url = get_gemini_endpoint("gemini-2.5-flash", "generateContent")
    
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []
    history = USER_CONVERSATIONS[user_id]
    
    context_note = f"\n[Context: Photos in buffer: {current_context.get('photos_count', 0)}, Active Heading: {current_context.get('active_heading')}, Active Instructions: {current_context.get('instructions')}]"
    
    contents = [
        {"role": "user", "parts": [{"text": INTELLIGENCE_SYSTEM_PROMPT + context_note}]},
        {"role": "model", "parts": [{"text": "Samajh gaya! Mai har user message ko analyze karke JSON me intent, friendly reply aur extracted data dunga."}]}
    ] + history[-6:] + [
        {"role": "user", "parts": [{"text": user_message}]}
    ]
    
    payload = {
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    # Primary: Gemini 2.5 Flash
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            raw_json = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_json)
            history.append({"role": "user", "parts": [{"text": user_message}]})
            history.append({"role": "model", "parts": [{"text": parsed.get("reply", "")}]})
            return parsed
    except Exception as e:
        print(f"Gemini error, trying Cloudflare fallback: {e}")
        
    # Secondary: Cloudflare Workers AI Fallback
    try:
        cf_raw = call_cloudflare_workers_ai(
            f"{context_note}\n\nUser message: {user_message}\nReturn strictly JSON with intent, reply, extracted_instruction, extracted_heading.",
            INTELLIGENCE_SYSTEM_PROMPT
        )
        parsed = clean_json_response(cf_raw)
        history.append({"role": "user", "parts": [{"text": user_message}]})
        history.append({"role": "model", "parts": [{"text": parsed.get("reply", "")}]})
        return parsed
    except Exception as e2:
        print(f"Cloudflare fallback error: {e2}")
        return {
            "intent": "CHAT",
            "reply": "Haan bhai, sun raha hoon! Batao kya instruction ya idea hai?",
            "extracted_instruction": None,
            "extracted_heading": None
        }

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
            
    prompt_text = f"{CAROUSEL_SYSTEM_PROMPT}\n\nUser Exact Heading / Topic:\n{user_heading}"
    if custom_instructions:
        prompt_text += f"\n\nSpecial User Instructions:\n{custom_instructions}"
        
    parts.append({"text": prompt_text})
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    # Primary: Gemini
    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
    except Exception as e:
        print(f"Gemini carousel generation error, falling back to Cloudflare Workers AI: {e}")
        
    # Secondary: Cloudflare Workers AI Llama 3.1 70B
    cf_res = call_cloudflare_workers_ai(
        prompt_text + "\n\nReturn strictly valid JSON only with keys: slide1, slide2, slide3, slide4, slide5.",
        CAROUSEL_SYSTEM_PROMPT
    )
    return clean_json_response(cf_res)
