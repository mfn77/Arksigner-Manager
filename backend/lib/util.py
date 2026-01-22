import os
import subprocess
from datetime import datetime
from pathlib import Path

DEFAULT_DEB_URL = "https://downloads.arksigner.com/files/arksigner-pub-2.3.12.deb"
DEFAULT_SUITE = "bullseye"
DEFAULT_MACHINE = "debian-arksigner"
DEFAULT_MIRROR = "http://deb.debian.org/debian"

OPT_DIR = Path("/opt/arksigner")
PKCS11_MODULE = OPT_DIR / "drivers/akis/x64/libakisp11.so"

SERVICE_CONTAINER = "arksigner-nspawn.service"
SERVICE_NATIVE = "arksigner-native.service"

SERVICE_CONTAINER_PATH = Path("/etc/systemd/system") / SERVICE_CONTAINER
SERVICE_NATIVE_PATH = Path("/etc/systemd/system") / SERVICE_NATIVE


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def sh(cmd: str, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["/bin/bash", "-lc", cmd], check=check, text=True, capture_output=True)


def require_root():
    if os.geteuid() != 0:
        raise SystemExit("ERROR: Must run as root (use pkexec).")


def ensure_pcscd_socket():
    # Best-effort; do not hard-fail if unit missing
    run(["systemctl", "enable", "--now", "pcscd.socket"], check=False)


def progress(pct: int, msg: str):
    # Machine-readable line for GUI
    try:
        pct = int(pct)
    except Exception:
        pct = 0
    pct = max(0, min(100, pct))
    print(f"PROGRESS {pct} {msg}", flush=True)


def system_status(unit: str) -> str:
    p = run(["systemctl", "is-active", unit], check=False)
    s = (p.stdout or "").strip()
    return s if s else "unknown"


def rootfs_dir(machine: str) -> Path:
    return Path("/var/lib/machines") / machine


def status(mode: str, machine: str) -> str:
    lines = []
    lines.append(f"[{ts()}] ArkSigner Manager status")
    lines.append(f"Mode:    {mode}")
    lines.append(f"Module:  {PKCS11_MODULE}")
    lines.append(f"pcscd.socket: {system_status('pcscd.socket')}")

    if mode == "container":
        rootfs = rootfs_dir(machine)
        lines.append(f"Machine: {machine}")
        lines.append(f"Rootfs:  {rootfs}")
        lines.append(f"{SERVICE_CONTAINER}: {system_status(SERVICE_CONTAINER)}")
        p = run(["machinectl", "list"], check=False)
        if (p.stdout or "").strip():
            lines.append("")
            lines.append(p.stdout.strip())
    else:
        lines.append(f"{SERVICE_NATIVE}: {system_status(SERVICE_NATIVE)}")

    return "\n".join(lines).strip() + "\n"

