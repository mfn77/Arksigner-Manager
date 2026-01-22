#!/usr/bin/env python3
import argparse
import os

from .util import (
    DEFAULT_DEB_URL,
    DEFAULT_MACHINE,
    DEFAULT_MIRROR,
    DEFAULT_SUITE,
    ensure_pcscd_socket,
    require_root,
    status,
    ts,
)
from .container_mode import (
    ensure_bind_mount_from_container,
    ensure_rootfs,
    enable_start_container,
    install_deb_inside_container,
    repair_container,
    uninstall_container,
)
from .native_mode import (
    deb_extract_to_opt,
    enable_start_native,
    patchelf_set_rpath,
    repair_native,
    uninstall_native,
)
from .download import download_deb
from .firefox import firefox_add
from .auto_version import find_latest_deb_url


def main():
    require_root()

    ap = argparse.ArgumentParser(prog="arksigner-manager-cli")
    ap.add_argument("--mode", choices=["container", "native"], default="container")
    ap.add_argument(
        "--action",
        required=True,
        choices=["install", "upgrade", "status", "repair", "uninstall", "purge"],
    )

    ap.add_argument("--deb", default=DEFAULT_DEB_URL, help="deb URL or local path (use 'auto' to find latest)")
    ap.add_argument("--suite", default=DEFAULT_SUITE, help="container: debootstrap suite")
    ap.add_argument("--mirror", default=DEFAULT_MIRROR, help="container: debootstrap mirror")
    ap.add_argument("--machine", default=DEFAULT_MACHINE, help="container: machine name")
    ap.add_argument("--recreate", action="store_true", help="container: recreate rootfs")

    ap.add_argument("--firefox-add", action="store_true", help="best-effort add PKCS#11 to Firefox (modutil)")
    ap.add_argument(
        "--native-rpath",
        action="store_true",
        help="native: opt-in set RPATH to $ORIGIN/libs using patchelf",
    )

    ap.add_argument("--user", default=os.environ.get("SUDO_USER", "") or os.environ.get("USER", "root"))
    ap.add_argument("--home", default=os.path.expanduser("~"))

    args = ap.parse_args()

    # Best-effort; do not hard fail if missing on some systems
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
    # Handle auto version detection
    deb_url = args.deb
    if deb_url == "auto":
        print(f"[{ts()}] Auto-detecting latest ArkSigner version...")
        detected_url = find_latest_deb_url()
        if not detected_url:
            raise SystemExit("ERROR: Failed to auto-detect latest version. Please specify --deb manually.")
        deb_url = detected_url
        print(f"[{ts()}] Using: {deb_url}")

    debp = download_deb(deb_url)

    extra = ""
    if args.mode == "container":
        # install can create rootfs; upgrade uses existing
        if args.action == "install":
            ensure_rootfs(args.machine, args.suite, args.mirror, recreate=args.recreate)
        else:
            ensure_rootfs(args.machine, args.suite, args.mirror, recreate=False)

        install_deb_inside_container(args.machine, debp)
        ensure_bind_mount_from_container(args.machine)
        enable_start_container(args.machine)
        out = status("container", args.machine)
    else:
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
