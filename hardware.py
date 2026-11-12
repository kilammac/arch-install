#!/usr/bin/env python3
"""Détection locale en lecture seule ; aucune installation ni sélection de disque."""
import json
import platform
import subprocess
from pathlib import Path


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def detect(sysroot=Path('/sys'), procroot=Path('/proc'), machine=None, probe_vm=True):
    dmi = sysroot / 'class/dmi/id'
    vendor = read(dmi / 'sys_vendor')
    model = read(dmi / 'product_name')
    cpuinfo = read(procroot / 'cpuinfo')
    cpu_vendors = sorted({line.split(':', 1)[1].strip()
                          for line in cpuinfo.splitlines()
                          if line.startswith('vendor_id') and ':' in line})
    arch = machine or platform.machine()
    warnings = []
    virtualization = 'unknown'
    if probe_vm:
        try:
            result = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True,
                                    text=True, timeout=5, check=False)
            value = result.stdout.strip()
            if result.returncode == 0 and value:
                virtualization = value
            elif result.returncode == 1 and value == 'none':
                virtualization = 'none'
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Complément DMI, utile si le bus systemd ou l'outil n'est pas disponible.
    signature = (vendor + ' ' + model).lower()
    if virtualization == 'unknown':
        for token, kind in [('qemu', 'qemu'), ('kvm', 'kvm'),
                            ('virtualbox', 'oracle'), ('vmware', 'vmware'),
                            ('virtual machine', 'microsoft'), ('parallels', 'parallels')]:
            if token in signature:
                virtualization = kind
                break
    chassis = read(dmi / 'chassis_type')
    batteries = any(read(p / 'type') == 'Battery'
                    for p in (sysroot / 'class/power_supply').glob('*'))
    laptop = batteries or chassis in {'8', '9', '10', '14', '30', '31', '32'}
    gpus = []
    for device in sorted((sysroot / 'bus/pci/devices').glob('*')):
        if not read(device / 'class').startswith('0x03'):
            continue
        driver = device / 'driver'
        gpus.append({'pci': device.name, 'vendor_id': read(device / 'vendor'),
                     'device_id': read(device / 'device'),
                     'driver': driver.resolve().name if driver.is_symlink() else None,
                     'boot_vga': read(device / 'boot_vga') == '1'})
    packages = {'linux-firmware', 'mesa'}
    if virtualization == 'none':
        if cpu_vendors == ['AuthenticAMD']:
            packages.add('amd-ucode')
        elif cpu_vendors == ['GenuineIntel']:
            packages.add('intel-ucode')
        else:
            warnings.append('Fabricant CPU inconnu : microcode à résoudre.')
    elif virtualization == 'unknown':
        warnings.append('Virtualisation indéterminée : choix du microcode à revalider sur le live.')
    vendors = {gpu['vendor_id'] for gpu in gpus}
    if '0x1002' in vendors:
        # VA-API AMD est fourni par mesa ; l'ancien nom n'est plus un paquet.
        packages.add('vulkan-radeon')
    if '0x8086' in vendors:
        packages.add('vulkan-intel')
        warnings.append('Décodage Intel : génération à vérifier avant choix du pilote VA-API.')
    if '0x10de' in vendors:
        warnings.append('NVIDIA détecté : résoudre la génération PCI et la branche compatible ; ne pas imposer nvidia-open aux anciennes cartes.')
    if not gpus:
        warnings.append('Aucun GPU PCI visible : accès limité ou affichage non PCI ; vérifier avant installation du bureau.')
    if virtualization in {'qemu', 'kvm'}:
        packages.add('qemu-guest-agent')
    elif virtualization == 'oracle':
        packages.add('virtualbox-guest-utils')
    elif virtualization == 'vmware':
        packages.add('open-vm-tools')
    elif virtualization not in {'none', 'unknown'}:
        warnings.append('Intégration invité à vérifier pour cette VM.')
    if arch != 'x86_64':
        warnings.append('Architecture non prise en charge par le live ISO Arch x86_64.')
    if virtualization == 'unknown':
        warnings.append('Détection VM incomplète : aucune supposition de machine physique.')
    return {'architecture': arch, 'supported_architecture': arch == 'x86_64',
            'manufacturer': vendor or None, 'model': model or None,
            'cpu_vendors': cpu_vendors, 'virtualization': virtualization,
            'form_factor': 'vm' if virtualization not in {'none', 'unknown'}
                           else ('laptop' if laptop else 'desktop-or-unknown'),
            'uefi': (sysroot / 'firmware/efi').exists(), 'gpus': gpus,
            'packages_suggested': sorted(packages),
            'asus_tools_available_as_option': virtualization == 'none' and 'asus' in vendor.lower(),
            'warnings': warnings,
            'scope': 'Machine exécutant la détection ; à recalculer sur le live cible.'}


def prepare_catalogue(rows, report):
    """Les choix logiciels restent transportables ; les paquets matériels sont recalculés."""
    managed = {'amd-ucode', 'intel-ucode', 'mesa', 'vulkan-radeon', 'vulkan-intel',
               'libva-mesa-driver', 'intel-media-driver', 'intel-gpu-tools',
               'nvidia-open-dkms', 'nvidia-utils', 'nvidia-settings', 'envycontrol',
               'lib32-mesa', 'lib32-vulkan-radeon', 'asusctl', 'rog-control-center',
               'qemu-guest-agent', 'virtualbox-guest-utils', 'open-vm-tools'}
    result = []
    for row in rows:
        row = dict(row)
        if row['kind'] == 'paquet' and row['name'] in managed:
            row.update(default=False, locked=True, group='00-materiel-automatique',
                       note='Calculé sur la machine cible ; voir hardware.py et le rapport matériel.')
        if row['name'] in {'asusctl', 'rog-control-center'} and report['asus_tools_available_as_option']:
            row.update(locked=False, note='Option ASUS détecté ; source du paquet à vérifier.')
        result.append(row)
    return result


if __name__ == '__main__':
    print(json.dumps(detect(), ensure_ascii=False, indent=2))
