"""Tests de profils matériels synthétiques, sans accès au disque système."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hardware import detect, prepare_catalogue
from selection import ROOT, make_plan


class DetectionTests(unittest.TestCase):
    def profile(self, cpu='AuthenticAMD', vendor='ASUSTeK COMPUTER INC.',
                model='G513QY', gpu_vendors=('0x1002', '0x1002'), vm='none'):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            def put(name, text):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            put('proc/cpuinfo', f'vendor_id : {cpu}\n')
            put('sys/class/dmi/id/sys_vendor', vendor)
            put('sys/class/dmi/id/product_name', model)
            put('sys/class/dmi/id/chassis_type', '10')
            for index, gpu_vendor in enumerate(gpu_vendors):
                device = f'sys/bus/pci/devices/0000:0{index}:00.0/'
                put(device + 'vendor', gpu_vendor)
                put(device + 'device', '0x1234')
                put(device + 'class', '0x030000')
            result = SimpleNamespace(stdout=vm, returncode=1 if vm == 'none' else 0)
            with patch('hardware.subprocess.run', return_value=result):
                return detect(base / 'sys', base / 'proc', machine='x86_64')

    def test_dual_amd_laptop(self):
        report = self.profile()
        self.assertEqual(len(report['gpus']), 2)
        self.assertEqual(report['form_factor'], 'laptop')
        self.assertIn('amd-ucode', report['packages_suggested'])
        self.assertTrue(report['asus_tools_available_as_option'])

    def test_intel_nvidia(self):
        report = self.profile(cpu='GenuineIntel', vendor='LENOVO',
                              gpu_vendors=('0x8086', '0x10de'))
        self.assertIn('intel-ucode', report['packages_suggested'])
        self.assertNotIn('amd-ucode', report['packages_suggested'])
        self.assertFalse(report['asus_tools_available_as_option'])
        self.assertTrue(any('NVIDIA' in w for w in report['warnings']))

    def test_vm_agents_without_host_microcode(self):
        for vm, package in [('kvm', 'qemu-guest-agent'), ('qemu', 'qemu-guest-agent'),
                            ('oracle', 'virtualbox-guest-utils'), ('vmware', 'open-vm-tools')]:
            with self.subTest(vm=vm):
                report = self.profile(vm=vm, gpu_vendors=('0x1af4',))
                self.assertIn(package, report['packages_suggested'])
                self.assertNotIn('amd-ucode', report['packages_suggested'])
                self.assertFalse(report['asus_tools_available_as_option'])

    def test_unknown_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = detect(root, root, machine='aarch64', probe_vm=False)
        self.assertEqual(report['virtualization'], 'unknown')
        self.assertFalse(report['supported_architecture'])
        self.assertTrue(report['warnings'])

    def test_portable_plan_without_encryption(self):
        report = self.profile(vm='kvm')
        rows = prepare_catalogue(json.loads((ROOT / 'catalogue/choix.json').read_text()), report)
        plan = make_plan(rows, {'pkg:amd-ucode', 'pkg:nvidia-utils', 'cfg:hypr'}, report)
        self.assertFalse(plan['target']['encryption'])
        self.assertEqual(plan['target']['profile'], 'auto')
        self.assertEqual(plan['packages'], [])
        self.assertIn('cfg:hypr', plan['selected_ids'])
        self.assertIn('qemu-guest-agent', plan['hardware_packages_preview'])


if __name__ == '__main__':
    unittest.main()
