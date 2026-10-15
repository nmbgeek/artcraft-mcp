# Run ArtCraft MCP on macOS

This fork builds the community ArtCraft MCP server as a native executable. It exposes 61 tools over stdio, including generation, uploads, job status, downloads, and account queries. It sends requests to ArtCraft's hosted API; it does not run generative models locally or automate PhotoCraft.

PhotoCraft has its own [MCP server](https://github.com/storytold/photocraft/blob/main/book/src/automation/mcp.md) for document editing. It is separate from this server.

## Build

Install Python 3.10 or newer, [Rust](https://rustup.rs), and the Xcode command line tools. On a Mac without the command line tools, run `xcode-select --install`.

From this repository:

```sh
PYTHONUTF8=1 python3 tools/build_native.py
PYTHONUTF8=1 python3 tools/artcraft_healthcheck.py --offline
```

The build downloads pinned dependencies from [ArtCraft's public source](https://github.com/storytold/artcraft/tree/d4e4ac69bbd93d237eaf5d0260bc6a5ff3a5e373) and uses the checked-in Cargo lockfile. It builds only this server, not the desktop application. The default is two compiler jobs. Allow several minutes and a few GB for the first build.

The resulting `bin/artcraft-mcp` matches the Mac used to compile it. An Apple Silicon build is arm64; an Intel Mac needs its own build. The checked-in `.exe` is for Windows. Native binary files are ignored by Git.

The same build helper supports Linux and Windows, where the Python command is usually `python` and the output ends in `.exe`. Windows rebuilds replace the bundled Windows executable in the working tree.

## Sign in

Install and sign in to the full ArtCraft application from its [official releases](https://github.com/storytold/artcraft/releases). Installing the Launcher or PhotoCraft alone does not establish an ArtCraft generation session.

The community server reads credentials at startup, in this order:

1. `ARTCRAFT_SESSION`, with optional `ARTCRAFT_AVT`.
2. `~/Artcraft/credentials/artcraft_session.txt`, with optional `artcraft_avt.txt`.
3. `~/Artcraft/credentials/native_session.json`, written by ArtCraft's native application.
4. The Tauri app's `ai.artcraft.app/.cookies` under the OS cache directory, then the legacy local data directory.

On macOS, the cookie locations are `~/Library/Caches/ai.artcraft.app/.cookies` and `~/Library/Application Support/ai.artcraft.app/.cookies`. On Windows the legacy location is `%LOCALAPPDATA%\ai.artcraft.app\.cookies`. Linux uses the platform cache and data directories, respecting XDG settings.

Only cookies for the ArtCraft API's `storyteller.ai` domain are used, and expired cookie entries are skipped. Credential files are read in place and are never copied into this repository or client configuration. Do not paste credentials into chat or commit them.

`ARTCRAFT_API_KEY` and `ARTCRAFT_MCP_PRIVATE_SESSION_TOKEN` are not implemented by this community server. Earlier documentation described a different modern server that is not included in this checkout.

Restart the MCP connection after signing in or changing accounts. Then verify read-only account access:

```sh
PYTHONUTF8=1 python3 tools/artcraft_healthcheck.py
```

This checks credits and an image cost estimate. It does not generate media or spend generation credits. A failed API call produces a nonzero exit status. Offline protocol success does not prove account access or generation.

## Connect your agents

For Claude Desktop, preview the exact path and then register it:

```sh
PYTHONUTF8=1 python3 setup_mcp.py --client 'Claude Desktop' --dry-run
PYTHONUTF8=1 python3 setup_mcp.py --client 'Claude Desktop'
```

The installer uses `~/Library/Application Support/Claude/claude_desktop_config.json`, preserves unrelated settings, and creates a `.bak` backup. Restart Claude Desktop afterward. Without `--client`, the installer also configures detected Cursor and Windsurf directories.

For Codex, register the absolute executable path using the [documented MCP configuration](https://developers.openai.com/codex/mcp):

```sh
codex mcp add artcraft -- "$PWD/bin/artcraft-mcp"
codex mcp get artcraft
```

Restart or reconnect the client's MCP session to load the new tools. Other stdio MCP clients can use:

```json
{
  "mcpServers": {
    "artcraft": {
      "command": "/absolute/path/to/artcraft-mcp/bin/artcraft-mcp",
      "args": []
    }
  }
}
```

Agents should discover tools with `tools/list`, use the returned parameter schemas, check credits, and estimate costs before submitting a generation. A typical workflow is `artcraft_estimate_cost`, `artcraft_generate_image`, `artcraft_get_job_status`, then `artcraft_download_media_file`. Generation requires account access and credits. This server does not automatically inherit every provider connection available in the desktop app.

## Verify changes

```sh
PYTHONUTF8=1 python3 -m unittest discover -s tests -v
cargo test --manifest-path rust/artcraft_mcp_cli/Cargo.toml --locked
PYTHONUTF8=1 python3 tools/artcraft_healthcheck.py --offline
```

Tests cover native executable selection, client config preservation, legacy automation tool names, credential precedence, cookie filtering, and actual subprocess JSON-RPC exchanges. CI runs native builds and offline checks on macOS, Windows, and Linux. A CI definition alone does not prove those platforms passed; check the individual run results.

The Python automation tools use `ARTCRAFT_MCP_PATH` or `ARTCRAFT_MCP_SERVER_PATH` when set, then search native binaries in this checkout and `PATH`. An invalid override fails explicitly. On Unix, discovery rejects `.exe` files and files without execute permission.

The companion FastAPI routes remain integration code for the original companion application, which provides its `core.logging` and `config` modules. They are not a standalone web server in this repository.
