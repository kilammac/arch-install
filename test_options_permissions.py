import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installer


class OptionsPermissionsTests(unittest.TestCase):
    def make_bundle(self, root):
        directory = root / 'opt/arch-personnel'
        directory.mkdir(parents=True, mode=0o700)
        for name, value in [('postinstall.py', 'print("test")\n'), ('options-differees.json', '[]\n')]:
            path = directory / name
            path.write_text(value)
            path.chmod(0o600)
        return directory

    def test_copytree_private_root_repaired_without_chmod_of_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_bundle(root / 'source')
            destination = root / 'installed'
            shutil.copytree(source, destination)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
            private = destination / 'other-file'
            private.write_text('local')
            private.chmod(0o600)
            installer.options_runtime_permissions(destination)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o755)
            self.assertEqual((destination / 'postinstall.py').stat().st_mode & 0o777, 0o644)
            self.assertEqual((destination / 'options-differees.json').stat().st_mode & 0o777, 0o644)
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_runtime_probe_precedes_execution_even_without_redeploy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_bundle(root)
            with patch('installer.TARGET', root), patch('installer.chroot') as chroot:
                installer.run_options('demo')
            calls = [call.args for call in chroot.call_args_list]
            self.assertEqual(calls[0][0], 'chown')
            self.assertIn('-c', calls[1])
            self.assertEqual(calls[2], ('visudo', '-cf', '/etc/sudoers'))
            self.assertEqual(calls[3][-2:], ('/opt/arch-personnel/postinstall.py', '--unattended'))
            self.assertIn('demo', calls[1])

    def test_missing_script_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                installer.options_runtime_permissions(Path(directory))


if __name__ == '__main__':
    unittest.main()
