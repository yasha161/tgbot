import os
import json

ASSETS_BASE_DIR = os.path.join(os.path.dirname(__file__), "saved_assets")
os.makedirs(ASSETS_BASE_DIR, exist_ok=True)

def _get_user_dir(chat_id: int) -> str:
    user_dir = os.path.join(ASSETS_BASE_DIR, str(chat_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def _get_index_file(chat_id: int) -> str:
    return os.path.join(_get_user_dir(chat_id), "index.json")

def _load_index(chat_id: int) -> dict:
    idx_path = _get_index_file(chat_id)
    if os.path.exists(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_index(chat_id: int, data: dict):
    idx_path = _get_index_file(chat_id)
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_user_asset(chat_id: int, tag: str, photo_bytes: bytes) -> str:
    clean_tag = tag.strip().lower().replace("@", "").replace("#", "")
    user_dir = _get_user_dir(chat_id)
    file_path = os.path.join(user_dir, f"{clean_tag}.jpg")
    
    with open(file_path, "wb") as f:
        f.write(photo_bytes)
        
    index = _load_index(chat_id)
    index[clean_tag] = file_path
    _save_index(chat_id, index)
    return clean_tag

def get_user_asset(chat_id: int, tag: str) -> str:
    clean_tag = tag.strip().lower().replace("@", "").replace("#", "")
    index = _load_index(chat_id)
    path = index.get(clean_tag)
    if path and os.path.exists(path):
        return path
    return None

def list_user_assets(chat_id: int) -> list:
    index = _load_index(chat_id)
    valid = []
    for tag, path in index.items():
        if os.path.exists(path):
            valid.append(tag)
    return sorted(valid)

def resolve_assets_from_text(chat_id: int, text: str) -> list:
    """
    Finds any @codeword or saved tags mentioned in the text and returns matching file paths.
    """
    index = _load_index(chat_id)
    words = text.lower().replace(",", " ").replace(";", " ").split()
    found_paths = []
    for word in words:
        clean = word.replace("@", "").replace("#", "").strip()
        if clean in index:
            p = index[clean]
            if os.path.exists(p) and p not in found_paths:
                found_paths.append(p)
    return found_paths
