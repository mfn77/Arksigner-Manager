"""
Automatically find the latest ArkSigner .deb version from downloads server.
"""
import re
import subprocess
from typing import Optional


def find_latest_deb_url(base_url: str = "https://downloads.arksigner.com/files/") -> Optional[str]:
    """
    Scrape the downloads page and find the latest arksigner-pub-*.deb file.
    Returns full URL or None if failed.
    
    Strategy:
    1. Download the directory listing HTML
    2. Parse all .deb filenames
    3. Extract version numbers
    4. Return highest version
    """
    try:
        # Download directory listing
        result = subprocess.run(
            ["curl", "-fsSL", base_url],
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )
        html = result.stdout
    except Exception as e:
        print(f"ERROR: Failed to fetch {base_url}: {e}")
        return None

    # Find all .deb files matching pattern: arksigner-pub-X.Y.Z.deb
    pattern = r'arksigner-pub-(\d+\.\d+\.\d+)\.deb'
    matches = re.findall(pattern, html)

    if not matches:
        print(f"ERROR: No .deb files found at {base_url}")
        return None

    # Parse versions and find highest
    versions = []
    for match in matches:
        try:
            parts = tuple(int(x) for x in match.split('.'))
            versions.append((parts, match))
        except ValueError:
            continue

    if not versions:
        print(f"ERROR: No valid version numbers found")
        return None

    # Sort by version tuple (major, minor, patch)
    versions.sort(reverse=True)
    highest_version = versions[0][1]
    
    url = f"{base_url}arksigner-pub-{highest_version}.deb"
    print(f"INFO: Auto-detected latest version: {highest_version}")
    print(f"INFO: URL: {url}")
    
    return url


if __name__ == "__main__":
    # Test
    url = find_latest_deb_url()
    if url:
        print(f"Latest: {url}")
    else:
        print("Failed to find latest version")
