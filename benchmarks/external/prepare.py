"""Fetch pinned public benchmark binaries/source into a new disposable directory.

Does not install system packages, configure agents, inspect credentials, start a
service, or download models. Requires macOS arm64, git, Bun, Node and uv on PATH.
"""

from pathlib import Path
import argparse
import hashlib
import urllib.request
import tarfile
import subprocess
import platform

ap = argparse.ArgumentParser()
ap.add_argument("destination", type=Path)
a = ap.parse_args()
if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise SystemExit("Published binary pins target macOS arm64; use upstream releases for your platform.")
base = a.destination
if base.exists() and any(base.iterdir()):
    raise SystemExit("Destination must be new or empty")
base.mkdir(parents=True, exist_ok=True)
assets = [
    (
        "codanna",
        "https://github.com/bartolli/codanna/releases/download/v0.17.1/codanna-0.17.1-macos-arm64.tar.xz",
        "158bea6911a38fba969e8d9ed206e6c5a365621f400c594d70718fb9040c3713",
    ),
    (
        "grepai",
        "https://github.com/yoanbernabeu/grepai/releases/download/v1.1.0/grepai_1.1.0_darwin_arm64.tar.gz",
        "85011455d817456afb2f99ceabd9437e893d51161046403826adae9b9c583660",
    ),
]
for name, url, checksum in assets:
    archive = base / url.rsplit("/", 1)[1]
    urllib.request.urlretrieve(url, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
        raise SystemExit("Checksum mismatch for " + name)
    dest = base / name
    dest.mkdir()
    with tarfile.open(archive) as t:
        t.extractall(dest, filter="data")
subprocess.run(["git", "clone", "https://github.com/tobi/qmd.git", str(base / "qmd")], check=True)
subprocess.run(["git", "checkout", "86d2365d17fc682e491c2c53d1e4a884aee8682a"], cwd=base / "qmd", check=True)
subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=base / "qmd", check=True)
subprocess.run(["uv", "venv", "--python", "3.12", str(base / "leann-env")], check=True)
subprocess.run(
    [
        "uv",
        "pip",
        "install",
        "--python",
        str(base / "leann-env/bin/python"),
        "-r",
        str(Path(__file__).parent / "requirements-leann.txt"),
    ],
    check=True,
)
print("Prepared tools. See README.md for explicit local model and RAVEL setup, then run measurements.")
