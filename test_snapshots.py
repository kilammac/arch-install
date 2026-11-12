import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import snapshots


class SnapshotsTests(unittest.TestCase):
    def test_none_manual_auto_have_distinct_packages(self):
        self.assertFalse(snapshots.packages('none'))
        self.assertEqual(snapshots.packages('manual'), {'snapper'})
        self.assertEqual(snapshots.packages('auto'), {'snapper', 'snap-pac'})

    def test_existing_snapshots_subvolume_is_preserved_and_config_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / 'etc/snapper/config-templates/default'
            template.parent.mkdir(parents=True)
            template.write_text('SUBVOLUME=""\nFSTYPE="btrfs"\nTIMELINE_CREATE="no"\n')
            marker = root / '.snapshots/marker'
            marker.parent.mkdir()
            marker.write_text('existing')
            chroot = Mock()
            snapshots.configure(root, 'auto', chroot)
            before = (root / 'etc/snapper/configs/root').read_text()
            snapshots.configure(root, 'auto', chroot)
            self.assertEqual(before, (root / 'etc/snapper/configs/root').read_text())
            self.assertIn('TIMELINE_CREATE="yes"', before)
            self.assertEqual(marker.read_text(), 'existing')
            self.assertEqual((root / 'etc/conf.d/snapper').read_text().count('SNAPPER_CONFIGS="root"'), 1)
            self.assertFalse(any('create-config' in call.args for call in chroot.call_args_list))

    def test_initial_snapshot_is_not_duplicated_on_resume(self):
        chroot = Mock(return_value='1 | arch-personnel-installation-initiale')
        snapshots.initial(chroot)
        self.assertEqual(chroot.call_count, 1)


if __name__ == '__main__':
    unittest.main()
