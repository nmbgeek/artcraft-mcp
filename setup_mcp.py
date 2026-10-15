#!/usr/bin/env python3
"""
ArtCraft MCP One-Click Installer & Configurator
Auto-detects installed MCP clients (Windsurf, Claude Desktop, Cursor) and registers artcraft-mcp.
"""

import os
import sys
import json
import argparse
from tools.artcraft_runtime import find_executable

def find_mcp_binary():
    return find_executable()


def get_target_configs():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        appdata = os.path.join(home, "Library", "Application Support")
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
    else:
        appdata = os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config"))
    
    configs = [
        # Windsurf / Codeium
        ("Windsurf", os.path.join(home, ".codeium", "windsurf", "mcp_config.json")),
        ("Windsurf (Alt)", os.path.join(home, ".windsurf", "mcp_config.json")),
        # Claude Desktop
        ("Claude Desktop", os.path.join(appdata, "Claude", "claude_desktop_config.json")),
        # Cursor
        ("Cursor", os.path.join(home, ".cursor", "mcp.json")),
    ]
    return configs

def register_mcp(config_path, client_name, exe_path):
    if not os.path.exists(os.path.dirname(config_path)):
        return False
    
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to parse existing {config_path}: {e}")
            print(f"[-] Aborting update for {client_name} to preserve existing configuration.")
            return False

    if not isinstance(data, dict):
        print(f"[-] Warning: Config at {config_path} is not a valid JSON object. Aborting.")
        return False

    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}

    data["mcpServers"]["artcraft"] = {
        "command": exe_path,
        "args": []
    }

    try:
        # Create a backup of the existing config if it exists
        if os.path.exists(config_path):
            import shutil
            shutil.copy2(config_path, config_path + ".bak")

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[+] Successfully registered ArtCraft MCP in {client_name} ({config_path})")
        return True
    except Exception as e:
        print(f"[-] Failed to write config to {config_path}: {e}")
        return False

def main():
    print("=== ArtCraft MCP One-Click Setup Utility ===")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show paths and config without writing files")
    parser.add_argument("--client", choices=["Claude Desktop", "Cursor", "Windsurf", "Windsurf (Alt)"],
                        help="Configure only this client; otherwise configure all detected clients")
    args = parser.parse_args()
    try:
        exe_path = find_mcp_binary()
    except FileNotFoundError as exc:
        parser.exit(1, f"{exc}\n")
    if args.dry_run:
        print(json.dumps({"mcpServers": {"artcraft": {"command": exe_path, "args": []}}}, indent=2))
        for name, path in get_target_configs():
            if args.client is None or args.client == name:
                print(f"{name}: {path}")
        return

    print(f"[*] Found ArtCraft MCP Binary: {exe_path}")
    
    updated_count = 0
    for name, path in get_target_configs():
        if args.client is not None and args.client != name:
            continue
        if register_mcp(path, name, exe_path):
            updated_count += 1

    if updated_count == 0:
        print("\n[*] No existing MCP client config files were automatically found.")
        print(f"Manual setup snippet for your mcp_config.json:\n")
        print(json.dumps({
            "mcpServers": {
                "artcraft": {
                    "command": exe_path,
                    "args": [],
                    "description": "ArtCraft AI platform MCP server",
                    "enabled": True
                }
            }
        }, indent=2))
    else:
        print(f"\n[+] Setup complete! ArtCraft MCP configured for {updated_count} client(s). Restart your MCP client to activate.")

if __name__ == "__main__":
    main()
