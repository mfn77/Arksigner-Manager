import shutil
import subprocess
from pathlib import Path

from .util import PKCS11_MODULE, ts


def firefox_add(user: str, home: str) -> str:
    if not PKCS11_MODULE.exists():
        return f"[{ts()}] Firefox add failed: module missing: {PKCS11_MODULE}\n"
    if shutil.which("modutil") is None:
        return f"[{ts()}] Firefox add failed: modutil not found (install nss-tools)\n"

    ffdir = Path(home) / ".mozilla/firefox"
    if not ffdir.exists():
        return (
            f"[{ts()}] Firefox add failed: Firefox profile dir not found: {ffdir}\n"
            "(Launch Firefox once first.)\n"
        )

    profiles = list(ffdir.glob("*.default*")) + list(ffdir.glob("*.default-release*"))
    if not profiles:
        return f"[{ts()}] Firefox add: no profiles found under {ffdir}\n"

    out = [f"[{ts()}] Adding PKCS#11 module to Firefox profiles (best-effort)\n"]
    for prof in profiles:
        if not prof.is_dir():
            continue
        cmd = [
            "sudo",
            "-u",
            user,
            "modutil",
            "-dbdir",
            f"sql:{prof}",
            "-add",
            "ArkSigner",
            "-libfile",
            str(PKCS11_MODULE),
        ]
        p = subprocess.run(cmd, text=True, capture_output=True)
        out.append(f"Profile: {prof}\nrc={p.returncode}\n")
        if p.stdout.strip():
            out.append(p.stdout.strip() + "\n")
        if p.stderr.strip():
            out.append(p.stderr.strip() + "\n")
        out.append("\n")
    return "".join(out)

