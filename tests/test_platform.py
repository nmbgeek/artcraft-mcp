import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import setup_mcp
from tools import artcraft_runtime as runtime
from tools.artcraft_healthcheck import successful, run_session


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'bin').mkdir()
        self.enterContext(patch.object(runtime, '__file__', str(self.root / 'tools/artcraft_runtime.py')))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(patch.object(runtime.shutil, 'which', return_value=None))

    def binary(self, name, executable=True):
        path = self.root / 'bin' / name
        path.write_text('test fixture')
        path.chmod(0o755 if executable else 0o644)
        return str(path.resolve())

    def test_macos_ignores_bundled_windows_binary(self):
        self.binary('artcraft-mcp.exe')
        with patch.object(runtime.sys, 'platform', 'darwin'):
            with self.assertRaises(FileNotFoundError):
                runtime.find_executable()
            native = self.binary('artcraft-mcp')
            self.assertEqual(runtime.find_executable(), native)

    def test_windows_selects_exe(self):
        exe = self.binary('artcraft-mcp.exe')
        self.binary('artcraft-mcp')
        with patch.object(runtime.sys, 'platform', 'win32'):
            self.assertEqual(runtime.find_executable(), exe)

    @unittest.skipIf(os.name == 'nt', 'Unix execute permissions')
    def test_unix_rejects_nonexecutable_and_invalid_override(self):
        native = self.binary('artcraft-mcp', executable=False)
        with patch.object(runtime.sys, 'platform', 'darwin'):
            with self.assertRaises(FileNotFoundError):
                runtime.find_executable(native)
            self.binary('artcraft-mcp')
            with patch.dict(os.environ, {'ARTCRAFT_MCP_PATH': '/does/not/exist'}):
                with self.assertRaises(FileNotFoundError):
                    runtime.find_executable()

    def test_claude_path_on_each_platform(self):
        for platform, expected in [('darwin', 'Library/Application Support/Claude'),
                                   ('win32', 'AppData/Roaming/Claude'),
                                   ('linux', '.config/Claude')]:
            with self.subTest(platform=platform), patch.object(setup_mcp.sys, 'platform', platform):
                path = dict(setup_mcp.get_target_configs())['Claude Desktop']
                self.assertIn(expected, path.replace('\\', '/'))

    def test_installer_preserves_other_config_and_backs_up(self):
        path = self.root / 'client.json'
        original = {'mcpServers': {'existing': {'command': 'keep'}}, 'theme': 'dark'}
        path.write_text(json.dumps(original))
        self.assertTrue(setup_mcp.register_mcp(str(path), 'Test', '/native/artcraft-mcp'))
        updated = json.loads(path.read_text())
        self.assertEqual(updated['mcpServers']['existing'], original['mcpServers']['existing'])
        self.assertEqual(updated['theme'], 'dark')
        self.assertEqual(json.loads(Path(str(path) + '.bak').read_text()), original)

    def test_invalid_client_json_is_not_overwritten(self):
        path = self.root / 'client.json'
        path.write_text('bad json')
        self.assertFalse(setup_mcp.register_mcp(str(path), 'Test', '/native/artcraft-mcp'))
        self.assertEqual(path.read_text(), 'bad json')

    def test_healthcheck_does_not_pass_tool_errors(self):
        self.assertFalse(successful({'result': {'isError': True, 'content': []}}))
        self.assertFalse(successful({'error': {'code': -32601}}))
        self.assertFalse(successful(None))
        self.assertTrue(successful({'result': {'isError': False, 'content': []}}))

    def test_healthcheck_timeout_is_bounded(self):
        import subprocess
        with patch('tools.artcraft_healthcheck.subprocess.run', side_effect=subprocess.TimeoutExpired('server', 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_session('/native/artcraft-mcp', [], timeout=1)


if __name__ == '__main__':
    unittest.main()

class AutomationContractTests(unittest.TestCase):
    def test_legacy_video_fields_preserve_requested_duration_and_frame(self):
        original = {'name': 'generate_video', 'arguments': {'prompt': 'test', 'model': 'seedance_2p0',
                    'duration': 8, 'start_frame_media_token': 'm_test'}}
        actual = runtime.normalize_tool_call(original)
        self.assertEqual(actual['name'], 'artcraft_generate_video')
        self.assertEqual(actual['arguments']['duration_seconds'], 8)
        self.assertEqual(actual['arguments']['start_frame_image_media_token'], 'm_test')
        self.assertIn('duration', original['arguments'])

    def test_upload_routes_by_media_type(self):
        for file, tool in [('image.png', 'image'), ('voice.wav', 'audio'), ('video.mp4', 'video')]:
            actual = runtime.normalize_tool_call({'name': 'upload_media', 'arguments': {'file_path': file}})
            self.assertEqual(actual['name'], f'artcraft_upload_{tool}')
        with self.assertRaises(ValueError):
            runtime.normalize_tool_call({'name': 'upload_media', 'arguments': {'file_path': 'unknown.zzzz'}})

    def test_legacy_prompt_uses_text(self):
        actual = runtime.normalize_tool_call({'name': 'create_prompt', 'arguments': {'prompt': 'test', 'is_negative': False}})
        self.assertEqual(actual, {'name': 'artcraft_create_prompt', 'arguments': {'text': 'test'}})

    def test_each_client_sends_canonical_tool_name(self):
        import importlib
        import io
        from types import SimpleNamespace
        for module, cls in [('runner', 'ArtCraftMCPClient'), ('3d_runner', 'ArtCraft3DClient'),
                            ('angle_matrix', 'ArtCraftAngleClient'), ('audio_weaver', 'ArtCraftAudioClient'),
                            ('cost_estimator', 'ArtCraftCostClient')]:
            client_type = getattr(importlib.import_module(f'tools.artcraft_{module}'), cls)
            client = client_type.__new__(client_type)
            client.req_id = 1
            client.proc = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO('{"result":{}}\n'))
            client.send_request('tools/call', {'name': 'get_job_status', 'arguments': {'job_token': 'jinf_test'}})
            wire = json.loads(client.proc.stdin.getvalue())
            self.assertEqual(wire['params']['name'], 'artcraft_get_job_status')
