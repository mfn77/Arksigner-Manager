import shutil
from pathlib import Path

from .util import progress, sh


def download_deb(deb: str) -> Path:
    progress(5, "Preparing download")
    out = Path("/tmp/arksigner.deb")

    if deb.startswith("http://") or deb.startswith("https://"):
        # Stage-based progress (can be upgraded later to parse curl %)
        progress(8, "Downloading .deb")
        sh(f"curl -fsSL '{deb}' -o '{out}'", check=True)
    else:
        src = Path(deb)
        if not src.exists() or not src.name.endswith(".deb"):
            raise SystemExit(f"ERROR: invalid --deb: {deb}")
        shutil.copy2(src, out)

    progress(15, "Downloaded .deb")
    return out

