import shutil
import tempfile
from pathlib import Path

from .util import (
    OPT_DIR,
    PKCS11_MODULE,
    SERVICE_NATIVE,
    SERVICE_NATIVE_PATH,
    ensure_pcscd_socket,
    progress,
    run,
)


def write_native_service():
    content = f"""[Unit]
Description=ArkSigner Service (native)
After=pcscd.socket
Requires=pcscd.socket

[Service]
Type=simple
User=root
Environment=LD_LIBRARY_PATH={OPT_DIR}/libs:/usr/local/lib64
ExecStart={OPT_DIR}/arksigner-universal
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    SERVICE_NATIVE_PATH.write_text(content, encoding="utf-8")


def deb_extract_to_opt(deb_path: Path):
    progress(40, "Extracting .deb to /opt/arksigner")

    if shutil.which("ar") is None:
        raise SystemExit("ERROR: 'ar' not found (install binutils).")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        shutil.copy2(deb_path, td / "pkg.deb")

        run(["ar", "x", str(td / "pkg.deb")], check=True)

        data = None
        for cand in td.glob("data.tar.*"):
            data = cand
            break
        if data is None:
            raise SystemExit("ERROR: data.tar.* not found in deb.")

        root = td / "root"
        root.mkdir(parents=True, exist_ok=True)
        run(["tar", "-xf", str(data), "-C", str(root)], check=True)

        src = root / "usr/bin/arksigner"
        if not src.exists():
            raise SystemExit("ERROR: deb content missing usr/bin/arksigner")

        OPT_DIR.mkdir(parents=True, exist_ok=True)

        # wipe existing tree for clean upgrade
        for child in list(OPT_DIR.iterdir()):
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except Exception:
                pass

        # copy; skip dotfiles
        for item in src.iterdir():
            if item.name.startswith("."):
                continue
            target = OPT_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

        # remove dotfiles that might slip
        for dot in OPT_DIR.rglob(".*"):
            try:
                if dot.is_file():
                    dot.unlink()
            except Exception:
                pass

        # ensure executables
        for exe in ["arksigner-universal", "arksigner-service"]:
            pexe = OPT_DIR / exe
            if pexe.exists():
                pexe.chmod(0o755)

        if not PKCS11_MODULE.exists():
            raise SystemExit(f"ERROR: PKCS#11 module missing after install: {PKCS11_MODULE}")

    progress(80, "Files installed to /opt/arksigner")


def patchelf_set_rpath() -> str:
    if shutil.which("patchelf") is None:
        return "RPATH requested but patchelf not found (install patchelf)\n"

    out = ["Applying RPATH ($ORIGIN/libs) to ArkSigner binaries (opt-in)\n"]
    targets = [OPT_DIR / "arksigner-universal", OPT_DIR / "arksigner-service"]

    for t in targets:
        if not t.exists():
            out.append(f"Skip missing: {t}\n")
            continue
        bak = t.with_name(t.name + ".bak")
        try:
            shutil.copy2(t, bak)
            p = run(["patchelf", "--set-rpath", "$ORIGIN/libs", str(t)], check=False)
            if p.returncode != 0:
                out.append(f"patchelf failed for {t}:\n{(p.stderr or '').strip()}\nRestoring backup.\n")
                shutil.copy2(bak, t)
            else:
                out.append(f"OK: {t}\n")
        except Exception as e:
            out.append(f"Error for {t}: {e}\nRestoring backup if present.\n")
            try:
                if bak.exists():
                    shutil.copy2(bak, t)
            except Exception:
                pass

    return "".join(out)


def enable_start_native():
    progress(92, "Enabling systemd service")
    write_native_service()
    run(["systemctl", "daemon-reload"], check=True)
    run(["systemctl", "stop", SERVICE_NATIVE], check=False)
    run(["systemctl", "reset-failed", SERVICE_NATIVE], check=False)
    run(["systemctl", "enable", "--now", SERVICE_NATIVE], check=True)
    progress(100, "Completed")


def uninstall_native(purge: bool):
    run(["systemctl", "stop", SERVICE_NATIVE], check=False)
    run(["systemctl", "disable", SERVICE_NATIVE], check=False)
    SERVICE_NATIVE_PATH.unlink(missing_ok=True)
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "reset-failed", SERVICE_NATIVE], check=False)

    if purge:
        shutil.rmtree(OPT_DIR, ignore_errors=True)


def repair_native():
    ensure_pcscd_socket()
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "reset-failed", SERVICE_NATIVE], check=False)
    run(["systemctl", "start", SERVICE_NATIVE], check=False)

