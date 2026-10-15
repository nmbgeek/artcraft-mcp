from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.build_native import install_binary


class NativeInstallTests(unittest.TestCase):
    def test_reinstall_replaces_inode_and_preserves_executable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / 'source', root / 'artcraft-mcp'
            source.write_bytes(b'new build')
            source.chmod(0o755)
            destination.write_bytes(b'old build')
            original_inode = destination.stat().st_ino
            install_binary(source, destination)
            self.assertEqual(destination.read_bytes(), b'new build')
            self.assertNotEqual(destination.stat().st_ino, original_inode)
            self.assertEqual(destination.stat().st_mode & 0o777, source.stat().st_mode & 0o777)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['artcraft-mcp', 'source'])

    def test_copy_failure_preserves_installed_binary_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'artcraft-mcp'
            destination.write_bytes(b'working build')
            with patch('tools.build_native.shutil.copy2', side_effect=OSError('copy failed')):
                with self.assertRaises(OSError):
                    install_binary(root / 'source', destination)
            self.assertEqual(destination.read_bytes(), b'working build')
            self.assertEqual([p.name for p in root.iterdir()], ['artcraft-mcp'])
