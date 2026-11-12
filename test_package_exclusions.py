"""Exclusions explicites, y compris lors d'une reprise d'une ancienne session."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installer
import postinstall
from hardware import prepare_catalogue


class PackageExclusionTests(unittest.TestCase):
    def test_normalize_preserves_other_options_and_order(self):
        self.assertEqual(postinstall.normalize_packages([
            'dsearch-bin', 'keep-one', 'flea-arch-git', 'keep-two', 'keep-one',
        ]), ['keep-one', 'keep-two'])
        for invalid in [None, 'dsearch-bin', ['bad/path'], [1]]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                postinstall.normalize_packages(invalid)

    def test_catalogue_disables_excluded_choices(self):
        rows = prepare_catalogue(json.loads((installer.ROOT / 'catalogue/choix.json').read_text()),
                                 {'asus_tools_available_as_option': False})
        excluded = [r for r in rows if r['name'] in postinstall.EXCLUDED_PACKAGES]
        self.assertEqual(len(excluded), 2)
        self.assertTrue(all(r['locked'] and not r['default'] for r in excluded))

    def test_saved_selection_is_migrated_without_losing_other_choices(self):
        settings = dict(user='demo', hostname='demo', timezone='Etc/UTC', keymap='us',
                        locale='fr_FR.UTF-8', login_shell='bash', boot='grub',
                        snapshot_mode='none', uefi=False,
                        payload_digest=hashlib.sha256((installer.ROOT / 'payload/manifest.json').read_bytes()).hexdigest(),
                        selected_ids=['pkg:dsearch-bin', 'pkg:fish', 'pkg:flea-arch-git', 'cfg:hypr'])
        selected = installer.validate_settings(settings, {'uefi': False, 'asus_tools_available_as_option': False})
        self.assertEqual(settings['selected_ids'], ['pkg:fish', 'cfg:hypr'])
        self.assertEqual({r['id'] for r in selected}, {'pkg:fish', 'cfg:hypr'})

    def test_package_plan_excludes_old_choices(self):
        available = '\n'.join('base base-devel linux linux-headers linux-lts linux-lts-headers linux-firmware btrfs-progs sudo networkmanager nano python git curl rsync pciutils usbutils dosfstools zram-generator mesa efibootmgr'.split())
        selected = [dict(id='pkg:' + name, kind='paquet', name=name) for name in
                    ['dsearch-bin', 'flea-arch-git', 'keep-option']]
        report = {'form_factor': 'vm', 'virtualization': 'kvm', 'gpus': [], 'uefi': True}
        with patch('installer.graphics', return_value=({'mesa'}, set())), patch('installer.subprocess.check_output', return_value=available), contextlib.redirect_stdout(io.StringIO()):
            official, deferred = installer.package_plan(selected, report)
        self.assertFalse(set(official) & postinstall.EXCLUDED_PACKAGES)
        self.assertEqual(deferred, ['keep-option'])

    def test_resume_refreshes_legacy_helper_and_filters_installed_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'opt/arch-personnel'
            directory.mkdir(parents=True, mode=0o700)
            script = directory / 'postinstall.py'
            script.write_text('# legacy helper\n')
            options = directory / 'options-differees.json'
            options.write_text(json.dumps(['dsearch-bin', 'keep-option', 'flea-arch-git']))
            with patch('installer.TARGET', root), patch('installer.chroot'):
                installer.prepare_options_runtime('demo')
            self.assertEqual(json.loads(options.read_text()), ['keep-option'])
            self.assertEqual(script.read_bytes(), (installer.ROOT / 'postinstall.py').read_bytes())
            self.assertEqual(directory.stat().st_mode & 0o777, 0o755)
            self.assertEqual(script.stat().st_mode & 0o777, 0o644)

    def test_only_excluded_options_never_bootstrap_or_invoke_yay(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'options.json'
            source.write_text(json.dumps(['dsearch-bin', 'flea-arch-git']))
            with patch('postinstall.os.geteuid', return_value=1000), patch('postinstall.save_failed') as save, patch('postinstall.subprocess.run') as run, patch('postinstall.shutil.which') as which, contextlib.redirect_stdout(io.StringIO()):
                postinstall.main(source)
            save.assert_called_once_with([])
            run.assert_not_called()
            which.assert_not_called()


if __name__ == '__main__':
    unittest.main()
