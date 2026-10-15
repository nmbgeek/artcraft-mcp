# ArtCraft MCP Rust server

`artcraft_mcp_cli/` is a standalone Cargo package exposing 61 tools over stdio. Its shared API/client crates come from the pinned public ArtCraft repository; a parent monorepo is no longer required.

```sh
cargo test --manifest-path rust/artcraft_mcp_cli/Cargo.toml --locked
PYTHONUTF8=1 python3 tools/build_native.py
```

The helper builds for the host and installs `bin/artcraft-mcp` on macOS/Linux or `bin/artcraft-mcp.exe` on Windows. See [native setup](../docs/macos.md) for credentials and agent configuration.

The bundled Windows executable is retained for existing users. It predates this fork's source fixes. Rebuild it to get current protocol and credential handling. The separate modern server mentioned in older documentation is not part of this repository.
