from datetime import datetime
from pathlib import Path

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def logs_dir() -> Path:
    d = Path.home() / ".local" / "state" / "arksigner-manager"
    d.mkdir(parents=True, exist_ok=True)
    return d

def gui_log(msg: str):
    try:
        p = logs_dir() / "gui.log"
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{now()}] {msg}\n")
    except Exception:
        pass

