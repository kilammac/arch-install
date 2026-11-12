"""Tests de sécurité et de déploiement ; aucune commande d'installation réelle."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installer
from deploy import config_packages, deploy
from hardware import prepare_catalogue


class InstallerTests(unittest.TestCase):
    def test_live_guard_before_commands(self):
        with patch('installer.os.geteuid', return_value=1000), patch('installer.run') as run:
            with self.assertRaises(RuntimeError):
                installer.live_required()
            run.assert_not_called()

    def test_bundle_integrity(self):
        installer.verify_bundle()

    def test_mounted_child_blocks_whole_disk(self):
        disk = {'name': '/dev/test', 'type': 'disk', 'size': 100, 'children': [
            {'name': '/dev/test1', 'type': 'part', 'mountpoints': ['/run/archiso/bootmnt']}]}
        self.assertFalse(installer.idle(disk))
        with patch('installer.blocks', return_value=[disk]):
            with self.assertRaises(RuntimeError):
                installer.revalidate(disk)

    def test_identity_and_layout_change_stop(self):
        disk = {'name': '/dev/test', 'type': 'disk', 'size': 100, 'serial': 'a'}
        for modified in [dict(disk, serial='b'), dict(disk, children=[{'name': '/dev/test1'}])]:
            with self.subTest(modified=modified), patch('installer.blocks', return_value=[modified]):
                with self.assertRaises(RuntimeError):
                    installer.revalidate(disk)

    def test_partition_names_and_boot_modes(self):
        for disk, expected in [('/dev/nvme0n1', '/dev/nvme0n1p2'), ('/dev/sda', '/dev/sda2'), ('/dev/vda', '/dev/vda2')]:
            for uefi in [True, False]:
                with self.subTest(disk=disk, uefi=uefi), patch('installer.revalidate'), patch('installer.run') as run:
                    root, esp = installer.partition({'name': disk}, uefi)
                    self.assertEqual(root, expected)
                    self.assertEqual(esp is not None, uefi)
                    calls = [c.args for c in run.call_args_list]
                    self.assertEqual(any(c[0] == 'mkfs.fat' for c in calls), uefi)

    def test_manual_rejects_same_root_and_esp(self):
        disk = {'children': [{'name': '/dev/vda1', 'type': 'part', 'size': 50 * 1024**3, 'fstype': 'vfat'}]}
        with patch('installer.ask', side_effect=['/dev/vda1', '/dev/vda1']):
            with self.assertRaises(RuntimeError):
                installer.manual_parts(disk, True)

    def test_gpu_generation_selection(self):
        report = {'gpus': [{'pci': '0000:01:00.0', 'vendor_id': '0x10de'}], 'packages_suggested': ['mesa']}
        with patch('installer.run', return_value='NVIDIA GA104M RTX 3080'):
            official, deferred = installer.graphics(report)
            self.assertIn('nvidia-open-dkms', official)
            self.assertFalse(deferred)
        with patch('installer.run', return_value='NVIDIA GP106 GTX 1060'):
            official, deferred = installer.graphics(report)
            self.assertNotIn('nvidia-open-dkms', official)
            self.assertIn('nvidia-580xx-dkms', deferred)

    def test_real_payload_deployment_in_temporary_directory(self):
        report = {'asus_tools_available_as_option': False}
        rows = prepare_catalogue(json.loads((installer.ROOT / 'catalogue/choix.json').read_text()), report)
        selected = [r for r in rows if r['kind'] == 'configuration' and r['default'] and not r['locked']]
        installed = config_packages(selected)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            deploy(target, 'demo', selected, 'fr', installed)
            home = target / 'home/demo'
            self.assertTrue((home / '.config/hypr/hyprland.lua').is_file())
            self.assertTrue((home / '.config/quickshell/cassette/DeckWindow.qml').is_file())
            self.assertTrue((home / '.config/nvim/init.lua').is_file())
            self.assertIn('kb_layout = "fr"', (home / '.config/hypr/modules/inputs.lua').read_text())
            self.assertNotIn('DP-9', (home / '.config/hypr/monitors.lua').read_text())
            self.assertNotIn('easyeffects', (home / '.config/hypr/modules/startup.lua').read_text())
            self.assertIn('firefox', (home / '.config/hypr/config/keymaps.lua').read_text())
            self.assertIn('/home/demo/', (home / '.config/systemd/user/quickshell.service').read_text())
            self.assertFalse((home / '.config/fish/fish_variables').exists())
            self.assertFalse((home / '.config/tmux/ssh_hosts').exists())
            self.assertTrue((target / 'usr/local/bin/start-desktop').is_file())


if __name__ == '__main__':
    unittest.main()
