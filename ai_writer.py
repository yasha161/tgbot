import os
import re
import json
import base64
import requests
from dotenv import load_dotenv
from json_repair import repair_json

from memory_store import (
    load_user_memory,
    add_message_to_history,
    get_recent_history_formatted,
    update_user_guidelines,
    get_user_guidelines_str,
    set_active_heading,
    get_active_heading,
    set_3d_mode,
    get_3d_mode,
    update_visual_directives,
    get_visual_directives
)

# Guarantee loading .env from bot directory
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "c6e9f428b957aecbe87557c7153155c0")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

CLOUDFLARE_MODELS = [
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/meta/llama-3.1-8b-instruct"
]

def call_cloudflare_ai(prompt: str, system_prompt: str = "") -> str:
    """
    Robust multi-tier Cloudflare Workers AI caller.
    Tries Llama 3.3 70B -> Llama 3.1 70B -> Llama 3.1 8B.
    """
    if not CLOUDFLARE_API_TOKEN:
        raise ValueError("Cloudflare API token not configured")
        
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    last_err = None
    for model in CLOUDFLARE_MODELS:
        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
        try:
            resp = requests.post(url, headers=headers, json={"messages": messages}, timeout=25)
            if resp.status_code == 200:
                res_data = resp.json().get("result", {})
                response_text = res_data.get("response")
                if not response_text and "choices" in res_data and len(res_data["choices"]) > 0:
                    response_text = res_data["choices"][0].get("message", {}).get("content", "")
                    
                if isinstance(response_text, dict):
                    return json.dumps(response_text)
                if response_text:
                    return str(response_text)
            else:
                last_err = f"{model} returned {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_err = f"{model} failed: {e}"
            
    raise RuntimeError(f"All Cloudflare AI models failed. Last error: {last_err}")

def call_gemini(prompt: str, system_prompt: str = "", image_paths: list = None) -> str:
    """
    Optional companion caller for Gemini 2.5 Flash with image support.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")
        
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
            
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    parts.append({"text": full_prompt})
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code == 200:
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text[:200]}")

def safe_parse_json(raw_text) -> dict:
    if isinstance(raw_text, dict):
        return raw_text
    if not raw_text:
        return {}
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
        
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    try:
        parsed = repair_json(cleaned, return_objects=True)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
            return parsed[0]
    except Exception as e:
        print(f"repair_json error: {e}")
        
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

MASTER_UNDERSTANDING_SYSTEM_PROMPT = """
You are Ron, an executive-level creative technologist and master Instagram Carousel art director.
You have the high intellect, context synthesis, and perceptive power of Antigravity.
You communicate in natural, sharp, executive Hinglish/English with zero robotic fluff.

CORE COMPREHENSION CAPABILITIES:
1. Master Multi-Turn History Synthesis:
   - When the user says "purani chat padho aur banao", "jo pehle topic bola tha uspe banao", "wahi topic continue karo", or gives an implicit reference, inspect [Recent Conversation History] carefully.
   - Extract the exact topic/heading previously discussed and lock it into `resolved_heading`.
   - If user provides a new topic in current message (e.g. "topic hai: Why 90% of Traders Lose Money", or "ispe banao: ..."), lock that into `resolved_heading`.

2. Natural Language Trigger Recognition (NO rigid codewords required):
   - User does NOT need to type secret codes like `312make`.
   - Words like "banao", "bana do", "make it", "shuru karo", "render karo", "chalo start karo", "ye photo leke bana do", "banao ispe" indicate `wants_render: true` and `intent: "RENDER"`.
   - Words like "heading ye rakhna", "topic hai", "naya topic" indicate `intent: "SET_TOPIC"`.
   - Words like "text chhota rakhna", "pet cover karna", "face mat cover karna", "yellow color" indicate `intent: "SET_INSTRUCTION"`.
   - If user is exploring ideas, discussing finance, or asking your view, set `intent: "CHAT"`.

3. Photo Count & Layout Request:
   - If user specifies photo count (e.g. "1 photo use karo", "single photo format", "use 4 photos", "pehli photo use karo", "only one image"):
     Extract `photo_count_requested`: 1, 2, 3, or 4.
   - If not mentioned, set to null.

4. Dynamic Visual Directives:
   - Floating icons: If user asks for "floating icons", "floating badge", "3d elements chahiye", "icons float karo":
     `visual_directives.floating_icons`: true.
   - Text position: If user asks for "text center me", "text beech me", "text upar/top", "text bottom/niche":
     `visual_directives.text_position`: "bottom" (default) | "center" | "top".
   - Text align: "center" (default) | "left" (if user asks for left-aligned or quote style).
   - Style: "3D" if 3D luxury elements are requested, otherwise "STUDIO".

5. Professional Executive Reply:
   - Respond in 1-2 direct, confident, articulate sentences in Hinglish/English.
   - Confirm the synthesized topic, photo count, and styling. No cheesy apologies or robotic formalities.

OUTPUT STRICTLY VALID JSON MATCHING THIS SCHEMA:
{
  "intent": "RENDER" | "SET_TOPIC" | "SET_INSTRUCTION" | "CHAT" | "STATUS" | "RESET",
  "wants_render": true | false,
  "needs_clarification": false,
  "resolved_heading": "The exact topic or headline to use, or null",
  "extracted_instruction": "Any specific guideline or rule to remember, or null",
  "style_mode": "3D" | "STUDIO" | null,
  "photo_count_requested": 1 | 2 | 3 | 4 | null,
  "visual_directives": {
    "floating_icons": true | false,
    "text_position": "bottom" | "center" | "top",
    "text_align": "center" | "left"
  },
  "reply": "Sharp, executive, competent Hinglish response"
}
"""

def analyze_user_message(user_id: int, user_message: str, current_context: dict) -> dict:
    # 1. Load memory state
    recent_history_text = get_recent_history_formatted(user_id, max_turns=20)
    saved_guidelines = get_user_guidelines_str(user_id)
    active_head = get_active_heading(user_id) or current_context.get("active_heading")
    is_3d = get_3d_mode(user_id) or current_context.get("is_3d", False)
    
    context_note = (
        f"[Current Session State]:\n"
        f"Buffered Photos Count: {current_context.get('photos_count', 0)}\n"
        f"Active Heading in Memory: {active_head}\n"
        f"Active 3D Mode: {is_3d}\n"
        f"Persistent Saved Guidelines: {saved_guidelines}\n\n"
        f"[Recent Conversation History]:\n"
        f"{recent_history_text or 'No previous history.'}\n\n"
        f"[User Message]:\n\"{user_message}\""
    )
    
    parsed = {}
    
    # 1. Primary Engine: Cloudflare Workers AI Llama 3.3 70B (Fast, high intellect, zero quota issues)
    try:
        raw_res = call_cloudflare_ai(context_note, MASTER_UNDERSTANDING_SYSTEM_PROMPT)
        parsed = safe_parse_json(raw_res)
    except Exception as e:
        print(f"Cloudflare master analysis notice: {e}")
        
    # 2. Secondary Engine: Gemini 2.5 Flash fallback
    if not parsed or "intent" not in parsed:
        try:
            raw_res = call_gemini(context_note, MASTER_UNDERSTANDING_SYSTEM_PROMPT)
            parsed = safe_parse_json(raw_res)
        except Exception as e2:
            print(f"Gemini fallback notice: {e2}")
            
    if not parsed or "intent" not in parsed:
        # Graceful fallback heuristic
        lower = user_message.lower()
        wants_render = any(k in lower for k in ["banao", "make", "render", "shuru", "start", "312make"])
        parsed = {
            "intent": "RENDER" if wants_render else "CHAT",
            "wants_render": wants_render,
            "needs_clarification": False,
            "resolved_heading": active_head,
            "extracted_instruction": None,
            "style_mode": "3D" if "3d" in lower else None,
            "photo_count_requested": 1 if "1 photo" in lower or "one photo" in lower else None,
            "visual_directives": {
                "floating_icons": "floating" in lower or "icon" in lower,
                "text_position": "bottom",
                "text_align": "center"
            },
            "reply": "Context captured. Ready to produce."
        }
        
    # Update persistent memory stores
    add_message_to_history(user_id, "user", user_message)
    add_message_to_history(user_id, "model", parsed.get("reply", ""))
    
    if parsed.get("resolved_heading"):
        set_active_heading(user_id, parsed["resolved_heading"])
        
    if parsed.get("extracted_instruction"):
        update_user_guidelines(user_id, parsed["extracted_instruction"])
        
    if parsed.get("style_mode") == "3D":
        set_3d_mode(user_id, True)
    elif parsed.get("style_mode") == "STUDIO":
        set_3d_mode(user_id, False)
        
    if parsed.get("visual_directives"):
        update_visual_directives(user_id, parsed["visual_directives"])
        
    return parsed

# Research-Backed Instagram Carousel Prompt
CAROUSEL_SYSTEM_PROMPT = """
You are a elite Instagram Carousel strategist and financial researcher specializing in high-retention wealth, investing, and personal compounding.

RESEARCH-DRIVEN CONTENT PRINCIPLES:
1. Deep Concrete Realities (No Generic Advice):
   - Use real mathematical comparisons (e.g. ₹10k/mo SIP @ 12% over 15 years = ₹50 Lakhs vs ₹10k in FD @ 6% = ₹29 Lakhs).
   - Use real economic principles (e.g. 7% inflation cuts real purchasing power by 50% in 10 years; Rule of 72; expense ratios of active vs index funds).
   - Unpopular, counter-intuitive truths (e.g. "Your bank account balance is losing purchasing power every single hour", "A car loan at 9% is an intentional wealth tax").

2. Strict Editorial Rhythm:
   - Slide 1: Exact verbatim user headline hook. Line 1 is punchy, Line 2 is the bridge ("here is the math most people ignore:").
   - Slide 2 (#1): The Hidden Trap / Shock Reality.
   - Slide 3 (#2): The Concrete Math / Tangible Comparison with bold numbers.
   - Slide 4 (#3): The Actionable Rule / Mindset Shift.
   - Slide 5: Compounding Anchor + High-Converting Save/Share CTA.

3. Strict Constraints:
   - Body copy (Slides 2-4): Exactly 1 to 2 concise lines per slide. Max 2 lines. Zero fluff.
   - Wrap all key stats, numbers, and power terms in <b>bold tags</b>.
   - Output strictly valid JSON matching this schema:
{
  "slide1": {
    "headline": "Verbatim User Hook (Line 1)",
    "highlight": "here is what you need to know:"
  },
  "slide2": {
    "title": "#1 – [Harsh Reality / Common Trap]",
    "lines": [
      "Savings accounts earn <b>~3% interest</b>, while inflation runs at <b>6% to 7%</b>.",
      "Idle money silently loses <b>real purchasing power</b> every single year."
    ]
  },
  "slide3": {
    "title": "#2 – [Tangible Proof / The Math]",
    "lines": [
      "A <b>₹10,000 monthly SIP</b> at 12% compounds to <b>₹50+ Lakhs</b> in 15 years.",
      "The cost of waiting 5 years to start is <b>₹24 Lakhs lost</b>."
    ]
  },
  "slide4": {
    "title": "#3 – [Discipline / System Rule]",
    "lines": [
      "Consistency always outperforms <b>market timing</b>.",
      "Automate your investments on salary day before <b>lifestyle creep</b> takes over."
    ]
  },
  "slide5": {
    "title": "Start early. Stay consistent. Let it compound.",
    "lines": [
      "The best time to start was <b>10 years ago</b>. The next best time is <b>today</b>.",
      "Save this post & share it with someone building their wealth. 💡"
    ],
    "cta": "SAVE & SHARE FOR LATER 📌"
  }
}
"""

def ensure_slide_keys(data: dict, fallback_heading: str) -> dict:
    default_structure = {
        "slide1": {
            "headline": fallback_heading,
            "highlight": "here is what you need to know:"
        },
        "slide2": {
            "title": "#1 – Your bank balance is NOT your wealth.",
            "lines": [
                "Savings accounts earn <b>~3% interest</b>, while real inflation eats <b>6% to 7%</b>.",
                "Idle cash silently loses <b>real purchasing power</b> every single year."
            ]
        },
        "slide3": {
            "title": "#2 – Saving protects, investing multiplies.",
            "lines": [
                "A <b>₹10,000/mo SIP</b> at 12% creates <b>~₹50.4 Lakhs</b> in 15 years.",
                "The exact same cash in a fixed deposit reaches only <b>~₹29 Lakhs</b>."
            ]
        },
        "slide4": {
            "title": "#3 – Consistency beats market timing.",
            "lines": [
                "You do not need a lump sum or daily trading skills to build wealth.",
                "An automated monthly SIP eliminates emotion and <b>compounds quietly</b>."
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
    
    if not isinstance(data, dict):
        return default_structure
        
    for key in ["slide1", "slide2", "slide3", "slide4", "slide5"]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = default_structure[key]
            
    if "headline" not in data["slide1"]:
        data["slide1"]["headline"] = fallback_heading
    if "highlight" not in data["slide1"]:
        data["slide1"]["highlight"] = "here is what you need to know:"
        
    for k in ["slide2", "slide3", "slide4", "slide5"]:
        if "title" not in data[k]:
            data[k]["title"] = default_structure[k]["title"]
        if "lines" not in data[k] or not isinstance(data[k]["lines"], list) or len(data[k]["lines"]) == 0:
            data[k]["lines"] = default_structure[k]["lines"]
            
    return data

def generate_carousel_content(user_heading: str, image_paths: list = None, custom_instructions: str = "") -> dict:
    prompt_text = f"Exact User Headline: {user_heading}"
    if custom_instructions:
        prompt_text += f"\n\nActive Custom Directives & Research Focus:\n{custom_instructions}"
        
    prompt_text += "\n\nSynthesize researched, high-retention 5-slide editorial copy in strictly valid JSON format."
    
    # 1. Primary: Cloudflare Workers AI Llama 3.3 70B
    try:
        raw_output = call_cloudflare_ai(prompt_text, CAROUSEL_SYSTEM_PROMPT)
        parsed = safe_parse_json(raw_output)
        if parsed and "slide1" in parsed:
            return ensure_slide_keys(parsed, user_heading)
    except Exception as e:
        print(f"Cloudflare carousel generation notice: {e}")
        
    # 2. Secondary: Gemini 2.5 Flash fallback
    try:
        raw_output = call_gemini(prompt_text, CAROUSEL_SYSTEM_PROMPT, image_paths)
        parsed = safe_parse_json(raw_output)
        if parsed and "slide1" in parsed:
            return ensure_slide_keys(parsed, user_heading)
    except Exception as e2:
        print(f"Gemini carousel generation notice: {e2}")
        
    return ensure_slide_keys({}, user_heading)
