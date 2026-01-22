#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

DEFAULT_DEB_URL = "https://downloads.arksigner.com/files/arksigner-pub-2.3.12.deb"
DEFAULT_SUITE = "bullseye"          # Debian 11
DEFAULT_MACHINE = "debian-arksigner"
DEFAULT_MIRROR = "http://deb.debian.org/debian"

# Install target (native) and bind target (container)
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
    # Do not hard-fail if unit missing; best effort
    run(["systemctl", "enable", "--now", "pcscd.socket"], check=False)

# --------------------------
# Firefox (best-effort)
# --------------------------
def firefox_add(user: str, home: str) -> str:
    if not PKCS11_MODULE.exists():
        return f"[{ts()}] Firefox add failed: module missing: {PKCS11_MODULE}\n"
    if shutil.which("modutil") is None:
        return f"[{ts()}] Firefox add failed: modutil not found (install nss-tools)\n"

    ffdir = Path(home) / ".mozilla/firefox"
    if not ffdir.exists():
        return f"[{ts()}] Firefox add failed: Firefox profile dir not found: {ffdir}\n(Launch Firefox once first.)\n"

    profiles = list(ffdir.glob("*.default*")) + list(ffdir.glob("*.default-release*"))
    if not profiles:
        return f"[{ts()}] Firefox add: no profiles found under {ffdir}\n"

    out = [f"[{ts()}] Adding PKCS#11 module to Firefox profiles (best-effort)\n"]
    for prof in profiles:
        if not prof.is_dir():
            continue
        cmd = ["sudo", "-u", user, "modutil", "-dbdir", f"sql:{prof}", "-add", "ArkSigner", "-libfile", str(PKCS11_MODULE)]
        p = subprocess.run(cmd, text=True, capture_output=True)
        out.append(f"Profile: {prof}\nrc={p.returncode}\n")
        if p.stdout.strip():
            out.append(p.stdout.strip() + "\n")
        if p.stderr.strip():
            out.append(p.stderr.strip() + "\n")
        out.append("\n")
    return "".join(out)

# --------------------------
# Status helpers
# --------------------------
def system_status(unit: str) -> str:
    p = run(["systemctl", "is-active", unit], check=False)
    s = (p.stdout or "").strip()
    return s if s else "unknown"

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

# ============================================================
# CONTAINER MODE
# ============================================================
def rootfs_dir(machine: str) -> Path:
    return Path("/var/lib/machines") / machine

def cleanup_unix_export(machine: str):
    exp = Path("/run/systemd/nspawn/unix-export") / machine
    sh(f"umount -lf '{exp}' 2>/dev/null || true", check=False)
    sh(f"rm -rf '{exp}' 2>/dev/null || true", check=False)

def terminate_container(machine: str):
    run(["systemctl", "stop", SERVICE_CONTAINER], check=False)
    run(["machinectl", "terminate", machine], check=False)
    cleanup_unix_export(machine)

def ensure_rootfs(machine: str, suite: str, mirror: str, recreate: bool):
    rootfs = rootfs_dir(machine)
    if recreate and rootfs.exists():
        terminate_container(machine)
        shutil.rmtree(rootfs, ignore_errors=True)

    if (rootfs / "etc/debian_version").exists():
        return

    rootfs.mkdir(parents=True, exist_ok=True)
    run(["debootstrap", suite, str(rootfs), mirror], check=True)

def download_deb(deb: str) -> Path:
    out = Path("/tmp/arksigner.deb")
    if deb.startswith("http://") or deb.startswith("https://"):
        sh(f"curl -fsSL '{deb}' -o '{out}'", check=True)
    else:
        src = Path(deb)
        if not src.exists() or not src.name.endswith(".deb"):
            raise SystemExit(f"ERROR: invalid --deb: {deb}")
        shutil.copy2(src, out)
    return out

def install_deb_inside_container(machine: str, deb_path: Path):
    rootfs = rootfs_dir(machine)
    (rootfs / "root").mkdir(parents=True, exist_ok=True)
    shutil.copy2(deb_path, rootfs / "root/arksigner.deb")

    cmd = (
        "set -e; export DEBIAN_FRONTEND=noninteractive;"
        "apt-get update -y;"
        "dpkg -i /root/arksigner.deb || true;"
        "apt-get -f install -y;"
        "dpkg -i /root/arksigner.deb || true;"
        "true"
    )
    run(["systemd-nspawn", "-D", str(rootfs), "/bin/bash", "-lc", cmd], check=True)

def ensure_bind_mount_from_container(machine: str):
    rootfs = rootfs_dir(machine)
    src = rootfs / "usr/bin/arksigner"
    if not src.exists():
        raise SystemExit("ERROR: container /usr/bin/arksigner missing; install failed.")

    OPT_DIR.mkdir(parents=True, exist_ok=True)
    sh(f"umount -lf '{OPT_DIR}' 2>/dev/null || true", check=False)
    sh(f"mount --bind '{src}' '{OPT_DIR}'", check=True)

    # Persist bind in fstab
    fstab_line = f"{src} {OPT_DIR} none bind 0 0"
    fstab_path = Path("/etc/fstab")
    fstab = fstab_path.read_text() if fstab_path.exists() else ""
    if fstab_line not in fstab:
        with open("/etc/fstab", "a", encoding="utf-8") as f:
            f.write(f"{fstab_line}\n")

    if not PKCS11_MODULE.exists():
        raise SystemExit(f"ERROR: PKCS#11 module missing at {PKCS11_MODULE}")

def write_container_service(machine: str):
    rootfs = rootfs_dir(machine)
    content = f"""[Unit]
Description=ArkSigner Debian Container (nspawn)
After=pcscd.socket
Requires=pcscd.socket

[Service]
Type=simple
ExecStart=/usr/bin/systemd-nspawn \\
  -D {rootfs} \\
  --machine={machine} \\
  --bind=/run/pcscd:/run/pcscd \\
  --bind-ro=/dev/bus/usb:/dev/bus/usb \\
  --console=passive \\
  --keep-unit \\
  /bin/bash -lc "/etc/init.d/arksignerd start; exec sleep infinity"
KillMode=mixed
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    SERVICE_CONTAINER_PATH.write_text(content, encoding="utf-8")

def enable_start_container(machine: str):
    write_container_service(machine)
    run(["systemctl", "daemon-reload"], check=True)
    terminate_container(machine)
    cleanup_unix_export(machine)
    run(["systemctl", "enable", "--now", SERVICE_CONTAINER], check=True)

def uninstall_container(machine: str, purge: bool):
    terminate_container(machine)
    run(["systemctl", "disable", SERVICE_CONTAINER], check=False)
    SERVICE_CONTAINER_PATH.unlink(missing_ok=True)
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "reset-failed", SERVICE_CONTAINER], check=False)

    sh(f"umount -lf '{OPT_DIR}' 2>/dev/null || true", check=False)

    rootfs = rootfs_dir(machine)
    src = rootfs / "usr/bin/arksigner"
    fstab_line = f"{src} {OPT_DIR} none bind 0 0"
    fstab_path = Path("/etc/fstab")
    if fstab_path.exists():
        orig = fstab_path.read_text().splitlines()
        new = [l for l in orig if l.strip() != fstab_line]
        fstab_path.write_text("\n".join(new) + ("\n" if new else ""), encoding="utf-8")

    if purge:
        shutil.rmtree(rootfs, ignore_errors=True)

def repair_container(machine: str):
    ensure_pcscd_socket()
    terminate_container(machine)
    cleanup_unix_export(machine)

    # Restore bind mount if possible
    if (rootfs_dir(machine) / "usr/bin/arksigner").exists():
        ensure_bind_mount_from_container(machine)

    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "reset-failed", SERVICE_CONTAINER], check=False)
    run(["systemctl", "start", SERVICE_CONTAINER], check=False)

# ============================================================
# NATIVE MODE
# ============================================================
def write_native_service():
    # LD_LIBRARY_PATH as default safe path. RPATH is opt-in.
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
    """
    Extract .deb -> data.tar.* -> copy usr/bin/arksigner tree into /opt/arksigner
    """
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

        # copy contents; skip dotfiles
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

def patchelf_set_rpath() -> str:
    """
    Opt-in: set RPATH to $ORIGIN/libs for key binaries.
    If patchelf fails, restore backups.
    """
    if shutil.which("patchelf") is None:
        return f"[{ts()}] RPATH requested but patchelf not found (install patchelf)\n"

    out = [f"[{ts()}] Applying RPATH ($ORIGIN/libs) to ArkSigner binaries (opt-in)\n"]
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
    write_native_service()
    run(["systemctl", "daemon-reload"], check=True)
    run(["systemctl", "stop", SERVICE_NATIVE], check=False)
    run(["systemctl", "reset-failed", SERVICE_NATIVE], check=False)
    run(["systemctl", "enable", "--now", SERVICE_NATIVE], check=True)

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

# --------------------------
# Main
# --------------------------
def main():
    require_root()

    ap = argparse.ArgumentParser(prog="arksigner-manager-cli")
    ap.add_argument("--mode", choices=["container", "native"], default="container")
    ap.add_argument("--action", required=True, choices=["install", "upgrade", "status", "repair", "uninstall", "purge"])

    ap.add_argument("--deb", default=DEFAULT_DEB_URL, help="deb URL or local path")
    ap.add_argument("--suite", default=DEFAULT_SUITE, help="container: debootstrap suite")
    ap.add_argument("--mirror", default=DEFAULT_MIRROR, help="container: debootstrap mirror")
    ap.add_argument("--machine", default=DEFAULT_MACHINE, help="container: machine name")
    ap.add_argument("--recreate", action="store_true", help="container: recreate rootfs")

    ap.add_argument("--firefox-add", action="store_true", help="best-effort add PKCS#11 to Firefox (modutil)")
    ap.add_argument("--native-rpath", action="store_true", help="native: opt-in set RPATH to $ORIGIN/libs using patchelf")

    ap.add_argument("--user", default=os.environ.get("SUDO_USER", "") or os.environ.get("USER", "root"))
    ap.add_argument("--home", default=os.path.expanduser("~"))

    args = ap.parse_args()

    ensure_pcscd_socket()

    # STATUS
    if args.action == "status":
        out = status(args.mode, args.machine)
        if args.firefox_add:
            out += "\n" + firefox_add(args.user, args.home)
        print(out, end="")
        return

    # REPAIR
    if args.action == "repair":
        if args.mode == "container":
            repair_container(args.machine)
            out = status("container", args.machine)
        else:
            repair_native()
            out = status("native", args.machine)
        if args.firefox_add:
            out += "\n" + firefox_add(args.user, args.home)
        print(out, end="")
        return

    # UNINSTALL / PURGE
    if args.action in ("uninstall", "purge"):
        purge = (args.action == "purge")
        if args.mode == "container":
            uninstall_container(args.machine, purge=purge)
        else:
            uninstall_native(purge=purge)
        print(f"[{ts()}] Uninstalled. mode={args.mode} purge={purge}\n", end="")
        return

    # INSTALL / UPGRADE
    debp = download_deb(args.deb)

    extra = ""
    if args.mode == "container":
        # install can create rootfs; upgrade uses existing
        if args.action == "install":
            ensure_rootfs(args.machine, args.suite, args.mirror, recreate=args.recreate)
        else:
            # upgrade: ensure rootfs exists; if missing, create
            ensure_rootfs(args.machine, args.suite, args.mirror, recreate=False)

        install_deb_inside_container(args.machine, debp)
        ensure_bind_mount_from_container(args.machine)
        enable_start_container(args.machine)
        out = status("container", args.machine)

    else:
        # native
        deb_extract_to_opt(debp)
        if args.native_rpath:
            extra = patchelf_set_rpath()
        enable_start_native()
        out = status("native", args.machine)
        if extra:
            out += "\n" + extra

    if args.firefox_add:
        out += "\n" + firefox_add(args.user, args.home)

    print(out, end="")

if __name__ == "__main__":
    main()

