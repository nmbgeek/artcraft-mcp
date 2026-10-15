"""Shared native executable discovery for setup and the automation tools."""

import os
from pathlib import Path
import shutil
import sys


def find_executable(override=None):
    """Find a server for this OS; never select a Windows executable on Unix."""
    windows = sys.platform == "win32"

    def usable(path):
        return (path.is_file() and (windows or path.suffix.lower() != ".exe")
                and (windows or os.access(path, os.X_OK)))

    explicit = override or os.environ.get("ARTCRAFT_MCP_PATH") or os.environ.get("ARTCRAFT_MCP_SERVER_PATH")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if usable(path):
            return str(path)
        raise FileNotFoundError(f"ArtCraft MCP override is not a runnable native executable: {path}")

    root = Path(__file__).resolve().parent.parent
    name = "artcraft-mcp.exe" if windows else "artcraft-mcp"
    directories = [root / "bin", root, root / "tools",
                   root / "rust/artcraft_mcp_cli/target/release",
                   root / "target/release"]
    for directory in directories:
        path = directory / name
        if usable(path):
            return str(path)
    path = shutil.which(name)
    if path and usable(Path(path)):
        return str(Path(path).resolve())
    raise FileNotFoundError(
        f"No native {name} found. Run PYTHONUTF8=1 python3 tools/build_native.py "
        "or set ARTCRAFT_MCP_PATH to a native executable."
    )


def normalize_tool_call(params):
    """Translate the automation scripts' legacy names to the community server API."""
    import mimetypes

    name = params['name']
    arguments = dict(params.get('arguments', {}))
    if name == 'upload_media':
        media_type = (mimetypes.guess_type(arguments.get('file_path', ''))[0] or '').split('/')[0]
        if media_type not in {'image', 'audio', 'video'}:
            raise ValueError('Cannot determine upload type. Use a recognized image, audio, or video extension.')
        name = f'artcraft_upload_{media_type}'
    elif not name.startswith('artcraft_'):
        name = 'artcraft_' + name
    if name == 'artcraft_generate_video':
        for old, new in [('duration', 'duration_seconds'), ('start_frame_media_token', 'start_frame_image_media_token'),
                         ('end_frame_media_token', 'end_frame_image_media_token')]:
            if old in arguments:
                arguments.setdefault(new, arguments.pop(old))
    if name == 'artcraft_create_prompt' and 'prompt' in arguments:
        if arguments.pop('is_negative', False):
            raise ValueError('The community create_prompt tool supports positive prompts only.')
        arguments['text'] = arguments.pop('prompt')
    return {**params, 'name': name, 'arguments': arguments}
