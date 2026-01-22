import shutil
from pathlib import Path

from .util import (
    OPT_DIR,
    PKCS11_MODULE,
    SERVICE_CONTAINER,
    SERVICE_CONTAINER_PATH,
    progress,
    rootfs_dir,
    run,
    sh,
)


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
        progress(18, "Recreating rootfs")
        terminate_container(machine)
        shutil.rmtree(rootfs, ignore_errors=True)

    if (rootfs / "etc/debian_version").exists():
        return

    progress(20, "Preparing Debian rootfs (debootstrap)")
    rootfs.mkdir(parents=True, exist_ok=True)
    run(["debootstrap", suite, str(rootfs), mirror], check=True)
    progress(45, "Debian rootfs ready")


def install_deb_inside_container(machine: str, deb_path: Path):
    progress(55, "Installing ArkSigner inside container")
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
    progress(75, "ArkSigner installed in container")


def ensure_bind_mount_from_container(machine: str):
    progress(85, "Binding ArkSigner to /opt/arksigner")
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
    progress(92, "Enabling systemd service")
    write_container_service(machine)
    run(["systemctl", "daemon-reload"], check=True)
    terminate_container(machine)
    cleanup_unix_export(machine)
    run(["systemctl", "enable", "--now", SERVICE_CONTAINER], check=True)
    progress(100, "Completed")


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
    # Best-effort cleanup for "busy / unix-export mount point exists / directory tree busy"
    terminate_container(machine)
    cleanup_unix_export(machine)

    # Try to unmount OPT_DIR if it is stuck busy
    sh(f"umount -lf '{OPT_DIR}' 2>/dev/null || true", check=False)

    # Restore bind mount if possible
    if (rootfs_dir(machine) / "usr/bin/arksigner").exists():
        ensure_bind_mount_from_container(machine)

    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "reset-failed", SERVICE_CONTAINER], check=False)
    run(["systemctl", "start", SERVICE_CONTAINER], check=False)

