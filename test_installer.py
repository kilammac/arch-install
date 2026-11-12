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
    def test_account_can_resume_after_useradd_without_creating_a_second_user(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            (root / 'etc/passwd').write_text('demo:x:1000:1000::/home/demo:/bin/bash\n')
            def account_only(session, name, label, action):
                if name == 'account':
                    return action()
            with patch('installer.TARGET', root), patch('installer.execute_step', side_effect=account_only), patch('installer.chroot') as chroot:
                installer.configure('demo', 'demo', 'us', 'Etc/UTC', 'fr_FR.UTF-8', {}, '', {}, [], [])
            self.assertFalse(any(call.args[0] == 'useradd' for call in chroot.call_args_list))
            self.assertTrue(any(call.args[0] == 'usermod' for call in chroot.call_args_list))

    def test_live_pacman_configuration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pacman.conf'
            path.write_text('[options]\n#ParallelDownloads = 5\n[core]\nInclude = /etc/pacman.d/mirrorlist\n#[multilib]\n#Include = /etc/pacman.d/mirrorlist\n')
            self.assertTrue(installer.prepare_live_pacman(path))
            self.assertFalse(installer.prepare_live_pacman(path))
            self.assertIn('ParallelDownloads = 5', path.read_text())
            self.assertEqual(path.read_text().count('\n[multilib]\n'), 1)
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

    def test_amd_old_vaapi_name_resolves_to_mesa(self):
        available = '\n'.join('base base-devel linux linux-headers linux-lts linux-lts-headers linux-firmware btrfs-progs sudo networkmanager nano python git curl rsync pciutils usbutils dosfstools zram-generator mesa vulkan-radeon efibootmgr'.split())
        report = {'form_factor': 'vm', 'virtualization': 'kvm', 'gpus': [], 'uefi': True}
        with patch('installer.graphics', return_value=({'mesa', 'libva-mesa-driver', 'vulkan-radeon'}, set())), patch('installer.subprocess.check_output', return_value=available):
            official, deferred = installer.package_plan([], report)
        self.assertIn('mesa', official)
        self.assertNotIn('libva-mesa-driver', official)
        self.assertFalse(deferred)

    def test_preview_never_calls_installation(self):
        with patch('sys.argv', ['installer.py', '--preview']), patch('installer.questionnaire'), patch('installer.live_required') as live, patch('installer.run') as run, patch('installer.UI.box'), patch('installer.UI.banner'), patch('installer.UI.header'):
            installer.main()
            live.assert_not_called()
            run.assert_not_called()

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
            # Une reprise au milieu du déploiement ne doit pas échouer sur les liens existants.
            deploy(target, 'demo', selected, 'fr', installed)


if __name__ == '__main__':
    unittest.main()
