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
    
    # Set LD_LIBRARY_PATH to include ArkSigner libs
    lib_dirs = [
        "/opt/arksigner/libs",
        "/opt/arksigner/drivers/akis/x64",
    ]
    ld_library_path = ":".join(lib_dirs)
    
    for prof in profiles:
        if not prof.is_dir():
            continue
        
        # First, try to delete existing module (ignore errors)
        del_cmd = [
            "sudo",
            "-u",
            user,
            "env",
            f"LD_LIBRARY_PATH={ld_library_path}",
            "modutil",
            "-dbdir",
            f"sql:{prof}",
            "-delete",
            "ArkSigner",
        ]
        subprocess.run(del_cmd, text=True, capture_output=True, input="\n\n")
        
        # Now add the module with LD_LIBRARY_PATH set
        cmd = [
            "sudo",
            "-u",
            user,
            "env",
            f"LD_LIBRARY_PATH={ld_library_path}",
            "modutil",
            "-dbdir",
            f"sql:{prof}",
            "-add",
            "ArkSigner",
            "-libfile",
            str(PKCS11_MODULE),
            "-force",
        ]
        
        # Use yes command to pipe enters to modutil
        full_cmd = f"yes '' | {' '.join(cmd)}"
        p = subprocess.run(
            full_cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=10
        )
        
        out.append(f"Profile: {prof}\n")
        
        # Success if rc is 0
        if p.returncode == 0:
            out.append("✓ Module added successfully\n")
        else:
            out.append(f"✗ Failed (rc={p.returncode})\n")
            
        # Only show actual errors, not prompts
        if p.stderr.strip():
            stderr_lines = [
                line for line in p.stderr.splitlines()
                if "ERROR:" in line and line.strip()
            ]
            if stderr_lines:
                out.append("\n".join(stderr_lines) + "\n")
        
        out.append("\n")
    return "".join(out)


def check_pkcs11_dependencies() -> str:
    """Check if PKCS11 module has all required dependencies"""
    if not PKCS11_MODULE.exists():
        return "Module not found"
    
    # Try to load the library to see what's missing
    result = subprocess.run(
        ["ldd", str(PKCS11_MODULE)],
        text=True,
        capture_output=True
    )
    
    missing = []
    for line in result.stdout.splitlines():
        if "not found" in line:
            lib = line.split()[0]
            missing.append(lib)
    
    if missing:
        return f"Missing libraries: {', '.join(missing)}\nInstall ArkSigner dependencies."
    return "All dependencies OK"
