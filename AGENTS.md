# AGENTS.md — ArtCraft MCP Project

Standalone project bundling all ArtCraft Model Context Protocol (MCP) server materials, precompiled binaries, automation CLI tools, agent skills, JSON schemas, and companion bridge routes.

## Fork workflow
- This checkout belongs to `nmbgeek/artcraft-mcp`. Keep changes, pushes, branches, and merges in this fork only.
- Never open pull requests against the upstream repository or push to upstream remotes.
- Use `codex/` branches for implementation, verify changes, then merge back into this fork's `main`.
- Check remote URLs before pushing. Reading pinned public upstream dependencies is allowed.
- Preserve unrelated local changes and agent configuration.

## Quick Facts
- **Binary Locations**:
  - `bin/artcraft-mcp` on macOS and Linux, built locally with `PYTHONUTF8=1 python3 tools/build_native.py`.
  - `bin/artcraft-mcp.exe` is the bundled Windows community edition.
  - The separate modern `artcraft-mcp-server` implementation is not included in this fork.
- **CLI Suite**: `.\tools\*.py` (requires Python 3.10+, `$env:PYTHONUTF8="1"`)
- **Agent Skill**: `.\skills\artcraft-mcp\SKILL.md`
- **Schemas**: `.\schemas\*.json` (61 tool definitions)
- **Rust Source**: `rust/artcraft_mcp_cli/`, with pinned public dependencies and a Cargo lockfile.

## Machine & Workspace Rules
- Always set `PYTHONUTF8=1` on every Python invocation.
- Do NOT run heavy builds or long GPU jobs without checking `/queue` or user permission.
- The community server uses session/visitor cookies. See `docs/macos.md` for supported credential sources. API keys and MCP private session tokens are not supported by this server.
- Use `PYTHONUTF8=1 python3 tools/artcraft_healthcheck.py --offline` for protocol verification without network or credits.
- Live checks must report API tool errors as failures. Never claim generation or authenticated access from an offline test.

## Common Verification Commands
```powershell
# Verify binary responds to JSON-RPC over stdio
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | .\bin\artcraft-mcp.exe

# Check credits and live balance
$env:PYTHONUTF8="1"; python tools\artcraft_cost_estimator.py --check-balance

# 1-Click setup across installed MCP clients
$env:PYTHONUTF8="1"; python setup_mcp.py
```
