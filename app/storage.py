from __future__ import annotations
import os, hashlib, datetime
from typing import Tuple

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _safe_name(name: str) -> str:
    # простая санитация
    name = name.replace("..", "").replace("/", "_").replace("\\", "_")
    return name

def save_upload(base_dir: str, user_id: int, filename: str, data: bytes) -> str:
    ensure_dir(base_dir)
    sub = os.path.join(base_dir, str(user_id))
    ensure_dir(sub)
    ext = os.path.splitext(filename)[1].lower() or ".bin"
    digest = hashlib.sha256(data).hexdigest()[:16]
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    fname = _safe_name(f"{stamp}_{digest}{ext}")
    path = os.path.join(sub, fname)
    with open(path, "wb") as f:
        f.write(data)
    return path
