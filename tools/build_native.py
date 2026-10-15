#!/usr/bin/env python3
"""Build and install the server for the current machine without a desktop build."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def install_binary(source, destination):
    """Replace the inode so macOS does not reuse a cached executable signature."""
    fd, temporary = tempfile.mkstemp(prefix=".artcraft-mcp-", dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2, help="Maximum concurrent compiler jobs")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if not shutil.which("cargo"):
        parser.error("Rust is required. Install it from https://rustup.rs, then retry.")
    root = Path(__file__).resolve().parent.parent
    target = root / "target"
    rust_info = subprocess.check_output(["rustc", "-vV"], text=True)
    host = next(line.split(": ", 1)[1] for line in rust_info.splitlines() if line.startswith("host: "))
    subprocess.run([
        "cargo", "build", "--release", "--locked", "--jobs", str(args.jobs),
        "--manifest-path", str(root / "rust/artcraft_mcp_cli/Cargo.toml"),
        "--target-dir", str(target), "--target", host,
    ], check=True)
    name = "artcraft-mcp.exe" if sys.platform == "win32" else "artcraft-mcp"
    destination = root / "bin" / name
    # Explicitly target the host even if Cargo has a global cross-compilation target.
    built = target / host / "release" / name
    if not built.is_file():
        raise SystemExit("Expected host binary missing. Unset Cargo build.target for a native build.")
    install_binary(built, destination)
    print(f"Installed native server: {destination}")


if __name__ == "__main__":
    main()
