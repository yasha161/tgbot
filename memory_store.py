import os
import json
import time
import shutil

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "chat_memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

def _get_user_file(user_id: int) -> str:
    return os.path.join(MEMORY_DIR, f"user_{user_id}.json")

def _get_user_pending_dir(user_id: int) -> str:
    pdir = os.path.join(MEMORY_DIR, f"user_{user_id}_pending")
    os.makedirs(pdir, exist_ok=True)
    return pdir

def load_user_memory(user_id: int) -> dict:
    fpath = _get_user_file(user_id)
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all default keys exist
                data.setdefault("history", [])
                data.setdefault("guidelines", [])
                data.setdefault("active_heading", None)
                data.setdefault("last_topic", None)
                data.setdefault("is_3d_mode", False)
                data.setdefault("visual_directives", {
                    "floating_icons": False,
                    "text_position": "bottom",
                    "text_align": "center",
                    "photo_count": None
                })
                return data
        except Exception as e:
            print(f"Memory read error: {e}")
            
    return {
        "history": [],
        "guidelines": [],
        "active_heading": None,
        "last_topic": None,
        "is_3d_mode": False,
        "visual_directives": {
            "floating_icons": False,
            "text_position": "bottom",
            "text_align": "center",
            "photo_count": None
        }
    }

def save_user_memory(user_id: int, data: dict):
    fpath = _get_user_file(user_id)
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Memory save error: {e}")

def add_message_to_history(user_id: int, role: str, text: str):
    data = load_user_memory(user_id)
    data["history"].append({
        "role": role,
        "text": text,
        "timestamp": time.time()
    })
    # Keep last 30 turns for comprehensive memory
    if len(data["history"]) > 30:
        data["history"] = data["history"][-30:]
    save_user_memory(user_id, data)

def get_recent_history_formatted(user_id: int, max_turns: int = 15) -> str:
    data = load_user_memory(user_id)
    hist = data.get("history", [])[-max_turns:]
    lines = []
    for h in hist:
        r = "USER" if h["role"] == "user" else "RON"
        lines.append(f"{r}: {h['text']}")
    return "\n".join(lines)

def update_user_guidelines(user_id: int, new_guideline: str):
    data = load_user_memory(user_id)
    if new_guideline and new_guideline not in data["guidelines"]:
        data["guidelines"].append(new_guideline)
        save_user_memory(user_id, data)

def get_user_guidelines_str(user_id: int) -> str:
    data = load_user_memory(user_id)
    return " | ".join(data.get("guidelines", []))

def set_active_heading(user_id: int, heading: str):
    data = load_user_memory(user_id)
    if heading:
        data["last_topic"] = data.get("active_heading")
        data["active_heading"] = heading
        save_user_memory(user_id, data)

def get_active_heading(user_id: int) -> str:
    data = load_user_memory(user_id)
    return data.get("active_heading")

def set_3d_mode(user_id: int, is_3d: bool):
    data = load_user_memory(user_id)
    data["is_3d_mode"] = bool(is_3d)
    save_user_memory(user_id, data)

def get_3d_mode(user_id: int) -> bool:
    data = load_user_memory(user_id)
    return data.get("is_3d_mode", False)

def update_visual_directives(user_id: int, directives: dict):
    data = load_user_memory(user_id)
    vdir = data.get("visual_directives", {})
    if isinstance(directives, dict):
        vdir.update(directives)
        data["visual_directives"] = vdir
        save_user_memory(user_id, data)

def get_visual_directives(user_id: int) -> dict:
    data = load_user_memory(user_id)
    return data.get("visual_directives", {
        "floating_icons": False,
        "text_position": "bottom",
        "text_align": "center",
        "photo_count": None
    })

# Persistent Pending Photos Management
def save_pending_photo(user_id: int, photo_bytes: bytes) -> str:
    pdir = _get_user_pending_dir(user_id)
    existing = sorted([f for f in os.listdir(pdir) if f.startswith("pending_") and f.endswith(".jpg")])
    next_idx = len(existing) + 1
    fpath = os.path.join(pdir, f"pending_{next_idx}.jpg")
    with open(fpath, "wb") as f:
        f.write(photo_bytes)
    return fpath

def get_pending_photos(user_id: int) -> list:
    pdir = _get_user_pending_dir(user_id)
    if not os.path.exists(pdir):
        return []
    files = sorted([os.path.join(pdir, f) for f in os.listdir(pdir) if f.startswith("pending_") and f.endswith(".jpg")])
    return files

def clear_pending_photos(user_id: int):
    pdir = _get_user_pending_dir(user_id)
    if os.path.exists(pdir):
        shutil.rmtree(pdir, ignore_errors=True)
    os.makedirs(pdir, exist_ok=True)

def reset_user_session(user_id: int):
    clear_pending_photos(user_id)
    data = load_user_memory(user_id)
    data["active_heading"] = None
    data["visual_directives"] = {
        "floating_icons": False,
        "text_position": "bottom",
        "text_align": "center",
        "photo_count": None
    }
    save_user_memory(user_id, data)
