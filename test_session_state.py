import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from session_state import Session
from recovery import resolve_layout, mount_existing, SUBVOLS
import installer

UUID = '11111111-2222-3333-4444-555555555555'


class SessionTests(unittest.TestCase):
    def test_external_backup_rejects_ram_and_read_only_media(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup'
            with patch('installer.subprocess.check_output', return_value='tmpfs\n'):
                with self.assertRaises(ValueError):
                    installer.backup_state_path(path)
            with patch('installer.subprocess.check_output', side_effect=['vfat\n', 'ro,umask=0077\n']):
                with self.assertRaises(ValueError):
                    installer.backup_state_path(path)
    def test_failure_survives_new_session_without_replaying_completed_step(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            session = Session.create({'hostname': 'demo'}, path)
            session.perform('filesystem', lambda: None)
            def fail():
                raise RuntimeError('Arrêt simulé')
            with self.assertRaises(RuntimeError):
                session.perform('base', fail)
            loaded = Session.load(path)
            self.assertTrue(loaded.done('filesystem'))
            self.assertEqual(loaded.data['in_progress'], 'base')
            with patch('builtins.print') as action:
                loaded.perform('filesystem', action)
                action.assert_not_called()
            loaded.perform('base', lambda: None)
            self.assertTrue(Session.load(path).done('base'))
            self.assertIsNone(Session.load(path).data['in_progress'])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_target_and_usb_copies_are_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / 'live/state.json', root / 'usb/state.json'
            session = Session.create({'hostname': 'demo'}, a)
            session.attach(b)
            session.perform('base', lambda: None)
            self.assertEqual(json.loads(a.read_text()), json.loads(b.read_text()))

    def test_secrets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for key in ['password', 'user_password', 'root_password', 'credentials']:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    Session.create({key: 'x'}, Path(directory) / 'state.json')

    def test_interrupted_format_is_never_restarted(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session.create({'hostname': 'demo'}, Path(directory) / 'state.json')
            session.data['in_progress'] = 'filesystem'
            with patch('installer.run') as run, patch('installer.partition') as partition:
                with self.assertRaises(RuntimeError):
                    installer.prepare_existing_session(session, {})
                run.assert_not_called()
                partition.assert_not_called()

    def test_uuid_resolves_new_device_name_and_rejects_changed_disk(self):
        disk = {'name': '/dev/vdb', 'type': 'disk', 'size': 48, 'model': None, 'serial': 'demo',
                'children': [{'name': '/dev/vdb2', 'mountpoints': [None]}]}
        layout = {'root_uuid': UUID, 'esp_uuid': None,
                  'disk_identity': {'size': 48, 'model': None, 'serial': 'demo'}}
        def run(*args, **kwargs):
            return '/dev/vdb2'
        _, root, _ = resolve_layout(layout, [disk], Path('/mnt/example'), run)
        self.assertEqual(root, '/dev/vdb2')
        disk['serial'] = 'another-disk'
        with self.assertRaises(RuntimeError):
            resolve_layout(layout, [disk], Path('/mnt/example'), run)

    def test_resume_mounts_only_and_checks_every_subvolume(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('recovery.mounted', return_value=None), patch('installer.run') as run:
                mount_existing(Path(directory), '/dev/vda2', None, {'root_uuid': UUID}, run)
            self.assertEqual(len(run.call_args_list), len(SUBVOLS))
            self.assertTrue(all(call.args[0] == 'mount' for call in run.call_args_list))
            with patch('recovery.mounted', return_value={'uuid': UUID, 'fsroot': '/wrong'}):
                with self.assertRaises(RuntimeError):
                    mount_existing(Path(directory), '/dev/vda2', None, {'root_uuid': UUID}, run)


if __name__ == '__main__':
    unittest.main()
