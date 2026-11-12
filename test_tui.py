import unittest
from unittest.mock import patch
from tui import Ui, retryable


class TuiTests(unittest.TestCase):
    def test_formatting_never_offers_retry(self):
        for name in ['mkfs.btrfs', 'mkfs.fat', 'wipefs', 'sgdisk', 'parted']:
            self.assertFalse(retryable([name, '/dev/vda']))
        self.assertTrue(retryable(['pacstrap', '/mnt/example', 'base']))
        self.assertTrue(retryable(['arch-chroot', '/mnt/example', 'mkinitcpio', '-P']))
    def test_selected_labels_and_returned_ids(self):
        ui = Ui()
        ui.gum = 'gum'
        with patch.object(ui, 'call', return_value='cfg:hypr') as call:
            selected = ui.multi('Configurations', [('Hyprland, raccourcis', 'cfg:hypr')], {'cfg:hypr'})
        self.assertEqual(selected, {'cfg:hypr'})
        args = call.call_args.args
        self.assertEqual(args[args.index('--selected') + 1], 'Hyprland · raccourcis')

    def test_family_then_fine_selection_and_configs(self):
        ui = Ui()
        rows = [dict(id='pkg:a', name='a', group='04-developpement', kind='paquet', default=True, locked=False),
                dict(id='pkg:b', name='b', group='04-developpement', kind='paquet', default=True, locked=False),
                dict(id='cfg:hypr', name='Hyprland', kind='configuration', default=True, locked=False)]
        with patch.object(ui, 'multi', side_effect=[{'04-developpement'}, {'pkg:a'}, {'cfg:hypr'}]), patch.object(ui, 'choose', return_value='oui'):
            selected = ui.selections(rows)
        self.assertEqual({r['id'] for r in selected}, {'pkg:a', 'cfg:hypr'})


if __name__ == '__main__':
    unittest.main()
