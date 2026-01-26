import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def _dev_repo_root() -> Path:
    """Find repo root from this file's location"""
    # This file: gui/core/privileged.py -> go up 3 levels
    here = Path(__file__).resolve()
    repo = here.parents[2]
    return repo


def find_backend_cli() -> str:
    """
    Find backend CLI for pkexec:
    1. Installed location (production)
    2. Dev repo location (development)
    """
    # Production paths
    installed_paths = [
        "/usr/libexec/arksigner-manager/arksigner-manager-cli",
        "/usr/lib/arksigner-manager/arksigner-manager-cli",
    ]

    for p in installed_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # Development: check if backend/arksigner_manager.py exists
    repo = _dev_repo_root()
    dev_backend = repo / "backend" / "arksigner_manager.py"

    if dev_backend.exists():
        # Return python command to run it directly
        return str(dev_backend)

    # Fallback
    cli = shutil.which("arksigner-manager-cli")
    if cli:
        return cli

    return installed_paths[0]  # Will fail clearly if not found


def build_pkexec_cmd(
    action: str,
    mode: str,
    machine: str,
    suite: str,
    deb: str,
    firefox_add: bool,
    recreate: bool,
    native_rpath: bool,
    force_terminate: bool = False,
    recreate_mounts: bool = False,
    clear_cache: bool = True,
) -> list[str]:
    """
    Build pkexec command for running backend with root privileges.
    In dev mode, runs Python directly without pkexec wrapper.
    """
    user = os.environ.get("USER", "")
    home = os.path.expanduser("~")

    backend_cli = find_backend_cli()
    repo = _dev_repo_root()

    # Check if we're in development mode
    is_dev = backend_cli.endswith("arksigner_manager.py")

    if is_dev:
        # Development mode: set PYTHONPATH to repo root
        py_path = str(repo)
        cmd = [
            "pkexec",
            "env",
            f"PYTHONPATH={py_path}",
            "python3",
            backend_cli,
        ]
    else:
        # Production mode: use installed paths
        installed_root = "/usr/share/arksigner-manager"
        cmd = [
            "pkexec",
            "env",
            f"PYTHONPATH={installed_root}",
            backend_cli,
        ]

    # Add arguments
    cmd.extend([
        "--action", action,
        "--mode", mode,
        "--machine", machine,
        "--suite", suite,
        "--deb", deb,
        "--user", user,
        "--home", home,
    ])

    if recreate:
        cmd.append("--recreate")
    if firefox_add:
        cmd.append("--firefox-add")
    if native_rpath:
        cmd.append("--native-rpath")
    if force_terminate:
        cmd.append("--force-terminate")
    if recreate_mounts:
        cmd.append("--recreate-mounts")
    if clear_cache:
        cmd.append("--clear-cache")

    return cmd


@dataclass
class RunResult:
    rc: int
    out: str
    err: str


def run_pkexec_stream(
    cmd: list[str],
    on_line: Callable[[str], None],
    on_progress: Callable[[int, str], None],
) -> RunResult:
    """
    Run pkexec and stream stdout live.
    Backend prints machine-readable progress lines:
        PROGRESS <pct> <message>
    """
    try:
        p = subprocess.Popen(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
    except Exception as e:
        err_msg = f"Failed to start process: {e}"
        on_line(err_msg)
        return RunResult(rc=1, out=err_msg, err=str(e))

    collected: list[str] = []
    try:
        assert p.stdout is not None
        for line in p.stdout:
            line = line.rstrip("\n")
            collected.append(line)
            on_line(line)

            if line.startswith("PROGRESS "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    try:
                        pct = int(parts[1].strip())
                        msg = parts[2].strip()
                        pct = max(0, min(100, pct))
                        on_progress(pct, msg)
                    except ValueError:
                        pass
    except Exception as e:
        collected.append(f"Stream error: {e}")
        on_line(f"Stream error: {e}")
    finally:
        rc = p.wait()

    text = "\n".join(collected).strip() + ("\n" if collected else "")
    return RunResult(rc=rc, out=text, err="")
