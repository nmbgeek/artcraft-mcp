#!/usr/bin/env python3
"""Verify the native MCP protocol, plus optional read-only account/API checks."""

import argparse
import json
from pathlib import Path
import subprocess

if __package__:
    from .artcraft_runtime import find_executable
else:
    from artcraft_runtime import find_executable


def find_binary(preferred=None):
    return Path(find_executable(preferred))


def run_session(binary_path, requests, timeout=60):
    wire = []
    for request in requests:
        wire.append(json.dumps(request))
        if request.get("method") == "initialize":
            wire.append(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    proc = subprocess.run([str(binary_path)], input="\n".join(wire) + "\n",
                          capture_output=True, text=True, timeout=timeout, check=True)
    responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    by_id = {response.get("id"): response for response in responses}
    return [by_id.get(request["id"]) for request in requests]


def successful(response):
    return (isinstance(response, dict) and "error" not in response
            and isinstance(response.get("result"), dict)
            and not response["result"].get("isError", False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Only initialize and list tools; no API calls")
    args = parser.parse_args()
    try:
        binary = find_binary()
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "artcraft-healthcheck", "version": "1.1.0"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        labels = ["MCP initialization", "Tool discovery"]
        if not args.offline:
            for name, arguments, label in [
                ("artcraft_get_credits", {}, "Account credits"),
                ("artcraft_estimate_cost", {"media_type": "image", "model": "flux_1_dev"}, "API cost estimate"),
            ]:
                requests.append({"jsonrpc": "2.0", "id": len(requests) + 1, "method": "tools/call",
                                 "params": {"name": name, "arguments": arguments}})
                labels.append(label)
        responses = run_session(binary, requests)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        parser.exit(1, f"[FAIL] Server check: {exc}\n")
    passed = True
    for index, (label, response) in enumerate(zip(labels, responses)):
        ok = successful(response)
        if ok and index == 0:
            ok = bool(response["result"].get("serverInfo"))
        if ok and index == 1:
            ok = bool(response["result"].get("tools"))
        passed = passed and ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if index == 1 and ok:
            print(f"  {len(response['result']['tools'])} tools registered")
        if not ok:
            print("  No successful result. Check ArtCraft login, network access, and server logs.")
    if not passed:
        parser.exit(1, "One or more checks failed.\n")
    print("Offline checks passed; account access was not tested." if args.offline else "Protocol and read-only API checks passed.")


if __name__ == "__main__":
    main()
