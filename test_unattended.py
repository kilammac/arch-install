"""Parcours automatique, mots de passe et retrait des autorisations temporaires."""
from contextlib import ExitStack, redirect_stdout
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import installer
import postinstall
from session_state import Session


class UnattendedTests(unittest.TestCase):
    def test_passwords_are_confirmed_and_resume_skips_completed_accounts(self):
        with patch('installer.getpass.getpass', side_effect=['one', 'two', 'user-value', 'user-value', 'root-value', 'root-value']), redirect_stdout(io.StringIO()):
            self.assertEqual(installer.collect_passwords('demo'), {'demo': 'user-value', 'root': 'root-value'})
        with tempfile.TemporaryDirectory() as directory:
            session = Session.create({'user': 'demo'}, Path(directory) / 'state.json')
            session.perform('password-set', lambda: None)
            with patch('installer.getpass.getpass', return_value='root-value') as prompt:
                self.assertEqual(installer.collect_passwords('demo', session), {'root': 'root-value'})
            self.assertEqual(prompt.call_count, 2)
            session.perform('root-password-set', lambda: None)
            with patch('installer.getpass.getpass') as prompt:
                self.assertEqual(installer.collect_passwords('demo', session), {})
                prompt.assert_not_called()

    def test_passwords_travel_only_over_stdin_and_are_discarded(self):
        credentials = {'demo': 'value:with spaces'}
        with patch('installer.subprocess.run') as run, patch('installer.UI.command') as logged:
            installer.set_password('demo', credentials)
        args, kwargs = run.call_args
        self.assertNotIn('value:with spaces', repr(args))
        self.assertEqual(args[0][-1], 'chpasswd')
        self.assertEqual(kwargs['input'], 'demo:value:with spaces\n')
        self.assertEqual(credentials, {})
        logged.assert_not_called()
        with patch('installer.subprocess.run') as run:
            with self.assertRaises(RuntimeError):
                installer.set_password('demo', {'demo': 'value\nroot:other'})
            run.assert_not_called()

    def test_password_failure_keeps_secret_out_of_error(self):
        credentials = {'demo': 'test-sensitive-value'}
        with patch('installer.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['chpasswd'])):
            with self.assertRaisesRegex(RuntimeError, 'Échec de définition') as error:
                installer.set_password('demo', credentials)
        self.assertNotIn('test-sensitive-value', str(error.exception))
        self.assertEqual(credentials, {})

    def test_user_and_root_password_stages_are_separate(self):
        def password_steps(session, name, label, action):
            if name in {'password-set', 'root-password-set'}:
                action()
        credentials = {'demo': 'user-value', 'root': 'root-value'}
        with patch('installer.execute_step', side_effect=password_steps), patch('installer.set_password') as apply:
            installer.configure('demo', 'demo', 'us', 'Etc/UTC', 'fr_FR.UTF-8', {}, '', {}, [], [], credentials=credentials)
        self.assertEqual([c.args[0] for c in apply.call_args_list], ['demo', 'root'])
        self.assertEqual(credentials, {})

    def test_temporary_sudo_is_restricted_and_removed_on_success_failure_and_interrupt(self):
        for failure in [None, RuntimeError, KeyboardInterrupt]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                with patch('installer.TARGET', target), patch('installer.chroot') as chroot:
                    def build():
                        with installer.options_sudo('demo'):
                            rule = target / installer.AUR_SUDO_RULE
                            self.assertEqual(rule.stat().st_mode & 0o777, 0o440)
                            self.assertEqual(rule.read_text(), 'demo ALL=(root) NOPASSWD: /usr/bin/pacman, /usr/bin/mkinitcpio\n')
                            chroot.assert_called_once_with('visudo', '-cf', '/etc/sudoers')
                            if failure:
                                raise failure()
                    if failure:
                        with self.assertRaises(failure):
                            build()
                    else:
                        build()
                    self.assertFalse((target / installer.AUR_SUDO_RULE).exists())
                    cleanup = (target / 'etc/tmpfiles.d/arch-personnel-aur.conf').read_text()
                    self.assertEqual(cleanup, f'r /{installer.AUR_SUDO_RULE}\n')

    def test_invalid_sudo_policy_is_removed_before_any_build(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with patch('installer.TARGET', target), patch('installer.chroot', side_effect=RuntimeError('visudo')):
                with self.assertRaises(RuntimeError):
                    with installer.options_sudo('demo'):
                        self.fail('Construction lancée avec une règle invalide')
            self.assertFalse((target / installer.AUR_SUDO_RULE).exists())

    def test_automatic_yay_bootstrap_install_and_cleanup_do_not_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / 'options.json'
            source.write_text('["keep-option"]')
            def command(args, **kwargs):
                if args[:2] == ['git', 'clone']:
                    (Path(args[-1]) / 'PKGBUILD').write_text('# test recipe\n')
                return SimpleNamespace(returncode=0)
            with patch('postinstall.os.geteuid', return_value=1000), patch('postinstall.Path.home', return_value=home), patch('postinstall.shutil.which', side_effect=[None, '/usr/bin/yay']), patch('postinstall.subprocess.run', side_effect=command) as run, patch('builtins.input', side_effect=AssertionError('Saisie tardive')), redirect_stdout(io.StringIO()):
                postinstall.main(source, unattended=True)
            calls = [c.args[0] for c in run.call_args_list]
            self.assertTrue(all(c.kwargs.get('stdin') == subprocess.DEVNULL for c in run.call_args_list))
            self.assertFalse(any('-v' in c for c in calls))
            makepkg = next(c for c in calls if c[0] == 'makepkg')
            self.assertIn('--noconfirm', makepkg)
            yay = next(c for c in calls if c[0] == '/usr/bin/yay')
            for flag in ['--noconfirm', '--answerclean', '--answerdiff', '--answeredit', '--removemake', '--sudoflags=-n']:
                self.assertIn(flag, yay)
            self.assertEqual(json.loads((home / '.local/state/arch-personnel/options-en-echec.json').read_text()), [])

    def test_failed_aur_is_recorded_without_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / 'options.json'
            source.write_text('["keep-option"]')
            with patch('postinstall.os.geteuid', return_value=1000), patch('postinstall.Path.home', return_value=home), patch('postinstall.shutil.which', return_value='/usr/bin/yay'), patch('postinstall.subprocess.run', side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]), patch('builtins.input', side_effect=AssertionError('Saisie tardive')), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    postinstall.main(source, unattended=True)
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(json.loads((home / '.local/state/arch-personnel/options-en-echec.json').read_text()), ['keep-option'])

    def test_main_does_not_ask_after_disk_confirmation(self):
        for reboot in [False, True]:
            with self.subTest(reboot=reboot), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                target = root / 'target'
                (target / 'var/log').mkdir(parents=True)
                runtime = root / 'runtime'
                disk = {'name': '/dev/test', 'size': 48 * 1024**3}
                report = {'supported_architecture': True, 'manufacturer': 'test', 'model': 'vm',
                          'cpu_vendors': [], 'gpus': [], 'uefi': False}
                credentials = {'demo': 'user-sensitive-value', 'root': 'root-sensitive-value'}
                def configure(*args):
                    self.assertIs(args[-1], credentials)
                    credentials.clear()
                mocks = {
                    'installer.TARGET': target, 'installer.RUNTIME': runtime,
                    'installer.live_required': None, 'installer.discover': [],
                    'installer.prepare_live_pacman': None, 'installer.detect': report,
                    'installer.questionnaire': ('demo', 'demo', 'us', 'fr_FR.UTF-8', 'Etc/UTC', [], 'bash', 'grub', 'none', reboot),
                    'installer.package_plan': (['base'], ['keep-option']),
                    'installer.collect_passwords': credentials, 'installer.choose_disk': disk,
                    'installer.revalidate': None, 'installer.partition': ('/dev/test2', None),
                    'installer.mount_root': None, 'installer.blocks': [disk],
                    'installer.uuid_of': '11111111-2222-3333-4444-555555555555',
                    'installer.verify_target': None,
                }
                for name, value in mocks.items():
                    stack.enter_context(patch(name, value) if name in {'installer.TARGET', 'installer.RUNTIME'} else patch(name, return_value=value))
                stack.enter_context(patch('sys.argv', ['installer.py']))
                stack.enter_context(patch('installer.configure', side_effect=configure))
                run = stack.enter_context(patch('installer.run', return_value=''))
                options = stack.enter_context(patch('installer.run_options'))
                stack.enter_context(patch('installer.ask', side_effect=AssertionError('Saisie tardive')))
                choose = stack.enter_context(patch.object(installer.UI, 'choose', side_effect=['effacer']))
                prompt = stack.enter_context(patch.object(installer.UI, 'input', side_effect=['INSTALLER /dev/test']))
                for method in ['header', 'box', 'banner']:
                    stack.enter_context(patch.object(installer.UI, method))
                stack.enter_context(patch.object(installer.UI, 'log', None))
                stack.enter_context(redirect_stdout(io.StringIO()))
                installer.main()
                self.assertEqual(choose.call_count, 1)
                self.assertEqual(prompt.call_count, 1)
                options.assert_called_once_with('demo', ['keep-option'])
                state = (runtime / 'state.json').read_text()
                self.assertNotIn('sensitive-value', state)
                self.assertNotIn('sensitive-value', (runtime / 'install.log').read_text())
                self.assertTrue(json.loads(state)['finished'])
                self.assertEqual(any(c.args == ('reboot',) for c in run.call_args_list), reboot)


if __name__ == '__main__':
    unittest.main()
