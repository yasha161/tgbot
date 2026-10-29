import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

COMPANION_SYSTEM_PROMPT = """
You are Ron, an AI creative partner and carousel strategist talking to your collaborator (Yash).
You have the exact personality of Antigravity: smart, warm, witty, supportive, highly competent, and conversational in Hindi / Hinglish.

Personality Guidelines:
- Talk like a real tech-savvy creative partner (use natural phrases like "Haan bro", "Bilkul sorted hai", "Ye angle kaafi tagda hai", "Samajh gaya mai").
- Do NOT sound robotic, repetitive, or overly formal.
- If the user shares an idea, hook, or asks a question, discuss it with genuine insights.
- If the user gives instructions (e.g. "heading meri hi rakhna", "short text rakhna", "ye rule yaad rakhna"), acknowledge it warmly and confirm you have locked it in memory.
- Keep responses concise, helpful, and natural (1 to 3 short paragraphs max).
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

def chat_with_agent(user_id: int, user_message: str) -> str:
    """
    Handles friendly conversation with memory like Antigravity.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []
        
    history = USER_CONVERSATIONS[user_id]
    
    # Append user turn
    history.append({"role": "user", "parts": [{"text": user_message}]})
    
    # Keep last 10 turns to avoid token bloat
    if len(history) > 10:
        history = history[-10:]
        USER_CONVERSATIONS[user_id] = history
        
    contents = [
        {"role": "user", "parts": [{"text": COMPANION_SYSTEM_PROMPT}]},
        {"role": "model", "parts": [{"text": "Samajh gaya bro! Mai hamesha Yash ke sath friendly, smart aur conversational Hinglish me connect rahunga, aur saare creative decisions me saath dunga."}]}
    ] + history
    
    payload = {"contents": contents}
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            model_reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            history.append({"role": "model", "parts": [{"text": model_reply}]})
            return model_reply
        else:
            return f"Bhai ek baar wapas bolo, network thoda choke hua ({resp.status_code})."
    except Exception as e:
        return f"Arre bro, thoda issue aaya: {str(e)}"

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
