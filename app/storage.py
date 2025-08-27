# app/storage.py
import json, os, tempfile, shutil
from typing import Any, Dict

def load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return _merge(default, data)
    except Exception:
        # write defaults if file missing/bad
        save_json_atomic(path, default)
        return default.copy()

def save_json_atomic(path: str, data: Dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=d)
    try:
        json.dump(data, tmp, indent=2)
        tmp.flush(); os.fsync(tmp.fileno())
        tmp.close()
        # backup old file
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        os.replace(tmp.name, path)
    finally:
        try: os.unlink(tmp.name)
        except: pass

def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = base.copy()
    for k,v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out
