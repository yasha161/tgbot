import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

INTELLIGENCE_SYSTEM_PROMPT = """
You are Ron, an elite AI creative partner and Instagram Carousel strategist (just like Antigravity).
You talk in warm, smart, witty Hindi/Hinglish (e.g. "Haan bro", "Samajh gaya bilkul", "Ye tagda idea hai", "Ekdum sorted").

Your job is to analyze the user's message and determine the INTENT:
1. "CHAT": The user is just chatting, asking a question, discussing an idea, greeting, or talking.
2. "INSTRUCTION": The user is giving a preference, rule, or guideline (e.g. "text 1 line hi rakhna", "blue tone rakhna", "heading meri hi use karna", "pet cover karna").
3. "TRIGGER_MAKE": The user wants to start making/rendering the carousel NOW (e.g. "bana do", "make it", "shuru karo", "chalu karo", "#make", "#banao", "#render", or giving a heading with photos).

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

# Per-user conversation memory
USER_CONVERSATIONS = {}

def analyze_user_message(user_id: int, user_message: str, current_context: dict) -> dict:
    """
    Uses Gemini intelligence to classify user intent, handle conversation,
    and detect instructions or work triggers.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []
    history = USER_CONVERSATIONS[user_id]
    
    context_note = f"\n[Context: Photos in buffer: {current_context.get('photos_count', 0)}, Active Heading: {current_context.get('active_heading')}, Active Instructions: {current_context.get('instructions')}]"
    
    # Prompt payload
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
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            raw_json = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_json)
            # Add to history
            history.append({"role": "user", "parts": [{"text": user_message}]})
            history.append({"role": "model", "parts": [{"text": parsed.get("reply", "")}]})
            return parsed
        else:
            return {
                "intent": "CHAT",
                "reply": "Bhai ek baar dobara bolo, connection thoda slow tha.",
                "extracted_instruction": None,
                "extracted_heading": None
            }
    except Exception as e:
        return {
            "intent": "CHAT",
            "reply": f"Bhai issue aaya: {str(e)}",
            "extracted_instruction": None,
            "extracted_heading": None
        }

def generate_carousel_content(user_heading: str, image_paths: list = None, custom_instructions: str = "") -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
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
    
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API Error ({resp.status_code}): {resp.text}")
        
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)
