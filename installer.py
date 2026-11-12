#!/usr/bin/env python3
"""Installateur live : étapes explicites, sans reprise du partitionnement."""
import argparse
import curses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hardware import detect, prepare_catalogue
from selection import ROOT, menu
from deploy import deploy, config_packages

TARGET = Path('/mnt/arch-personnel')


def run(*args, capture=False):
    print('+', ' '.join(str(a) for a in args), flush=True)
    result = subprocess.run([str(a) for a in args], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ''


def ask(prompt, default='', pattern=None):
    while True:
        value = input(f'{prompt}' + (f' [{default}]' if default else '') + ' : ').strip() or default
        if value and (pattern is None or re.fullmatch(pattern, value)):
            return value
        print('Valeur invalide.')


def write(relative, text, mode=0o644):
    path = TARGET / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def verify_bundle():
    manifest = json.loads((ROOT / 'payload/manifest.json').read_text())
    for relative, expected in manifest.items():
        path = ROOT / 'payload' / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink():
            raise ValueError(f'Chemin refusé dans le manifeste : {relative}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Fichier absent ou modifié : {relative}')
    print(f'Configurations embarquées vérifiées : {len(manifest)} fichiers.')


def live_required():
    if os.geteuid() != 0 or not Path('/run/archiso').is_dir():
        raise RuntimeError('Refus : utiliser le live ISO Arch comme root.')
    if os.uname().machine != 'x86_64':
        raise RuntimeError('Seul Arch x86_64 est pris en charge.')
    if TARGET.exists() and any(TARGET.iterdir()):
        raise RuntimeError(f'{TARGET} non vide : inspecter/démonter la tentative précédente avant de continuer.')
    if subprocess.run(['mountpoint', '-q', str(TARGET)]).returncode == 0:
        raise RuntimeError('Cible déjà montée ; aucune reprise automatique du formatage.')
    # L'ISO Arch ne démarre normalement pas sous Secure Boot, mais vérifier aussi efivarfs.
    for variable in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        data = variable.read_bytes()
        if len(data) > 4 and data[4] == 1:
            raise RuntimeError('Désactiver Secure Boot pour cette installation.')


def blocks():
    result = subprocess.check_output(['lsblk', '--json', '--bytes', '--paths',
        '--output', 'NAME,TYPE,SIZE,MODEL,SERIAL,RO,RM,MOUNTPOINTS,FSTYPE,MAJ:MIN'], text=True)
    return json.loads(result)['blockdevices']


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get('children', []))


def idle(node):
    return not any(n.get('ro') or any(n.get('mountpoints') or [])
                   for n in flatten([node]))


def fingerprint(node):
    return tuple(tuple(str(n.get(k)) for k in ('name', 'size', 'model', 'serial', 'maj:min', 'type', 'fstype'))
                 for n in flatten([node]))


def choose_disk():
    nodes = blocks()
    disks = [n for n in nodes if n['type'] == 'disk' and idle(n)
             and int(n['size']) >= 40 * 1024**3]
    print('\nDisques disponibles (au moins 40 Gio, aucun montage ou swap actif) :')
    for i, disk in enumerate(disks, 1):
        print(i, disk['name'], disk.get('model'), f'{int(disk["size"])/1024**3:.1f} Gio',
              '(amovible)' if disk.get('rm') else '')
    if not disks:
        raise RuntimeError('Aucun disque admissible. Démonter la cible si nécessaire ; ne pas démonter la clé contenant cet outil.')
    number = int(ask('Numéro du disque cible', pattern=r'[1-9][0-9]*'))
    if number > len(disks):
        raise RuntimeError('Numéro de disque inconnu.')
    return disks[number - 1]


def revalidate(disk):
    current = next((n for n in blocks() if n['name'] == disk['name']), None)
    if not current or fingerprint(current) != fingerprint(disk) or not idle(current):
        raise RuntimeError('Identité ou état du disque modifié : opération annulée.')


def graphics(report):
    packages = set(report['packages_suggested'])
    extra = set()
    for gpu in report['gpus']:
        name = run('lspci', '-nn', '-s', gpu['pci'], capture=True)
        if gpu['vendor_id'] == '0x8086':
            if re.search(r'Sandy|Ivy|Haswell|Broadwell', name, re.I):
                packages.add('libva-intel-driver')
            else:
                packages.add('intel-media-driver')
        if gpu['vendor_id'] != '0x10de':
            continue
        if re.search(r'\b(?:TU|GA|AD|GB)[0-9]{3}', name):
            packages.update(['nvidia-open-dkms', 'nvidia-utils'])
        elif re.search(r'\b(?:GM|GP|GV)[0-9]{3}', name):
            print('Ancienne génération NVIDIA : pilote 580xx proposé après redémarrage ; nouveau reste disponible dans le noyau pour le premier démarrage.')
            extra.update(['nvidia-580xx-dkms', 'nvidia-580xx-utils'])
        else:
            print('Génération NVIDIA non reconnue automatiquement :', name)
            choice = ask('Pilote : nouveau / open / 580xx (vérifier la compatibilité)', 'nouveau', r'nouveau|open|580xx')
            if choice == 'open':
                packages.update(['nvidia-open-dkms', 'nvidia-utils'])
            elif choice == '580xx':
                extra.update(['nvidia-580xx-dkms', 'nvidia-580xx-utils'])
    return packages, extra


def package_plan(selected, report):
    fixed = set('base base-devel linux linux-headers linux-lts linux-lts-headers linux-firmware btrfs-progs sudo networkmanager nano python git curl rsync pciutils usbutils dosfstools zram-generator'.split())
    hw, extra = graphics(report)
    requested = {r['name'] for r in selected if r['kind'] == 'paquet'}
    required = fixed | config_packages(selected) | hw
    if report['form_factor'] == 'laptop' and report['virtualization'] == 'none':
        required.add('power-profiles-daemon')
    # Empêcher la transplantation de réglages d'amorçage/dépôts de l'ancien système.
    requested -= {'update-grub', 'chaotic-keyring', 'chaotic-mirrorlist', 'snapper-rollback'}
    if 'steam' in requested:
        if any(g['vendor_id'] == '0x1002' for g in report['gpus']):
            required.update(['lib32-mesa', 'lib32-vulkan-radeon'])
        if any(g['vendor_id'] == '0x8086' for g in report['gpus']):
            required.update(['lib32-mesa', 'lib32-vulkan-intel'])
        if 'nvidia-utils' in hw:
            required.add('lib32-nvidia-utils')
    required.add('efibootmgr' if report['uefi'] else 'grub')
    available = set(subprocess.check_output(['pacman', '-Slq', 'core', 'extra', 'multilib'], text=True).splitlines())
    missing = required - available
    if missing:
        raise RuntimeError('Paquets requis absents des dépôts : ' + ', '.join(sorted(missing)))
    official = required | (requested & available)
    deferred = (requested - available) | extra
    if 'yay-bin' in deferred:
        deferred.remove('yay-bin')
        deferred.add('yay')  # construire le helper depuis son PKGBUILD AUR
    # Ces programmes de session ne doivent pas concurrencer le Quickshell personnel.
    print('\nPaquets officiels :', ' '.join(sorted(official)))
    print('Options à installer après redémarrage :', ' '.join(sorted(deferred)) or 'aucune')
    print('Un paquet absent des dépôts sera recherché dans AUR, sans supposer son origine.')
    return sorted(official), sorted(deferred)


def partition(disk, uefi):
    revalidate(disk)
    path = disk['name']
    run('wipefs', '--all', path)
    run('sgdisk', '--zap-all', path)
    if uefi:
        run('sgdisk', '-n', '1:0:+2G', '-t', '1:ef00', '-c', '1:EFI', path)
    else:
        run('sgdisk', '-n', '1:0:+2M', '-t', '1:ef02', '-c', '1:BIOS', path)
    run('sgdisk', '-n', '2:0:0', '-t', '2:8300', '-c', '2:Arch', path)
    run('partprobe', path)
    run('udevadm', 'settle')
    prefix = path + ('p' if path[-1].isdigit() else '')
    root = prefix + '2'
    esp = prefix + '1' if uefi else None
    if esp:
        run('mkfs.fat', '-F32', '-n', 'EFI', esp)
    return root, esp


def manual_parts(disk, uefi):
    if not uefi:
        raise RuntimeError('Le mode partitions existantes exige UEFI ; le mode effacement prend aussi en charge BIOS.')
    parts = [n for n in flatten(disk.get('children', [])) if n['type'] == 'part']
    for n in parts:
        print(n['name'], n.get('fstype'), f'{int(n["size"])/1024**3:.1f} Gio')
    root = ask('Partition réservée à Arch (elle sera formatée en Btrfs)', pattern=r'/dev/[a-zA-Z0-9/_-]+')
    esp = ask('Partition EFI existante FAT32 (conservée)', pattern=r'/dev/[a-zA-Z0-9/_-]+')
    by_name = {n['name']: n for n in parts}
    if root == esp or root not in by_name or esp not in by_name:
        raise RuntimeError('Choisir deux partitions distinctes du disque affiché.')
    if int(by_name[root]['size']) < 40 * 1024**3:
        raise RuntimeError('La partition racine doit faire au moins 40 Gio.')
    if by_name[esp]['fstype'] != 'vfat' or int(by_name[esp]['size']) < 1024**3:
        raise RuntimeError('ESP FAT32 de 1 Gio minimum requise pour les deux noyaux. Préparer une ESP dédiée si nécessaire.')
    esp_type = run('blkid', '-s', 'PART_ENTRY_TYPE', '-o', 'value', esp, capture=True).lower()
    if esp_type != 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b':
        raise RuntimeError('La partition choisie doit avoir le type GPT EFI System Partition.')
    # Vérifier l'espace avant le formatage de la racine, puis démonter pour revalider le disque.
    with tempfile.TemporaryDirectory(prefix='arch-esp-', dir='/run') as directory:
        run('mount', '-o', 'ro,nosuid,nodev,noexec', esp, directory)
        try:
            if shutil.disk_usage(directory).free < 700 * 1024**2:
                raise RuntimeError('Moins de 700 Mio libres sur l’ESP : préparer une ESP plus grande.')
        finally:
            run('umount', directory)
    return root, esp


def mount_root(root, esp):
    run('mkfs.btrfs', '-f', '-L', 'ArchRoot', root)
    TARGET.mkdir(parents=True, exist_ok=True)
    run('mount', root, TARGET)
    subvols = {'@': '', '@home': 'home', '@log': 'var/log', '@pkg': 'var/cache/pacman/pkg', '@snapshots': '.snapshots'}
    for subvol in subvols:
        run('btrfs', 'subvolume', 'create', TARGET / subvol)
    run('umount', TARGET)
    run('mount', '-o', 'subvol=@,compress=zstd:3,noatime', root, TARGET)
    for subvol, path in subvols.items():
        if path:
            (TARGET / path).mkdir(parents=True, exist_ok=True)
            run('mount', '-o', f'subvol={subvol},compress=zstd:3,noatime', root, TARGET / path)
    if esp:
        (TARGET / 'boot').mkdir(exist_ok=True)
        run('mount', '-o', 'umask=0077', esp, TARGET / 'boot')
        free = shutil.disk_usage(TARGET / 'boot').free
        if free < 700 * 1024**2:
            raise RuntimeError('Moins de 700 Mio libres sur l’ESP ; arrêt avant pacstrap.')


def chroot(*args, capture=False):
    return run('arch-chroot', TARGET, *args, capture=capture)


def configure(user, hostname, keymap, timezone, locale, report, root, disk, selected, deferred, login_shell='bash'):
    fstab = run('genfstab', '-U', TARGET, capture=True)
    write('etc/fstab', fstab + '\n')
    write('etc/hostname', hostname + '\n')
    write('etc/hosts', f'127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {hostname}.localdomain {hostname}\n')
    write('etc/locale.gen', 'en_US.UTF-8 UTF-8\nfr_FR.UTF-8 UTF-8\n')
    write('etc/locale.conf', f'LANG={locale}\n')
    write('etc/vconsole.conf', f'KEYMAP={keymap}\n')
    chroot('ln', '-sf', '/usr/share/zoneinfo/' + timezone, '/etc/localtime')
    chroot('hwclock', '--systohc')
    chroot('locale-gen')
    chroot('useradd', '-m', '-G', 'wheel', '-s', '/usr/bin/fish' if login_shell == 'fish' else '/bin/bash', user)
    write('etc/sudoers.d/10-wheel', '%wheel ALL=(ALL:ALL) ALL\n', 0o440)
    chroot('visudo', '-cf', '/etc/sudoers')
    print('\nDéfinis le mot de passe du compte (aucun chiffrement du disque).')
    chroot('passwd', user)
    # Compte root verrouillé, administration via sudo et compte wheel.
    chroot('usermod', '-L', 'root')
    write('etc/systemd/zram-generator.conf', '[zram0]\nzram-size = min(ram / 2, 8192)\ncompression-algorithm = zstd\n')
    write('etc/mkinitcpio.conf.d/10-personnel.conf', 'HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck)\n')
    chroot('mkinitcpio', '-P')
    if report['uefi']:
        # L'entrée amovible permet aussi le démarrage si le firmware refuse la NVRAM.
        try:
            chroot('bootctl', '--esp-path=/boot', 'install')
        except subprocess.CalledProcessError:
            chroot('bootctl', '--esp-path=/boot', '--no-variables', 'install')
        uuid = run('blkid', '-s', 'UUID', '-o', 'value', root, capture=True)
        write('boot/loader/loader.conf', 'default arch.conf\ntimeout 5\nconsole-mode keep\neditor no\n')
        for kernel, title in [('linux', 'Arch Linux'), ('linux-lts', 'Arch Linux LTS')]:
            filename = 'arch.conf' if kernel == 'linux' else 'arch-lts.conf'
            write('boot/loader/entries/' + filename,
                  f'title {title}\nlinux /vmlinuz-{kernel}\ninitrd /initramfs-{kernel}.img\noptions root=UUID={uuid} rootflags=subvol=@ rw\n')
    else:
        chroot('grub-install', '--target=i386-pc', disk['name'])
        chroot('grub-mkconfig', '-o', '/boot/grub/grub.cfg')
    chroot('systemctl', 'enable', 'NetworkManager.service', 'systemd-timesyncd.service')
    installed = set(chroot('pacman', '-Qq', capture=True).splitlines())
    for pkg, unit in [('bluez', 'bluetooth.service'), ('cups', 'cups.service'),
                      ('power-profiles-daemon', 'power-profiles-daemon.service'),
                      ('qemu-guest-agent', 'qemu-guest-agent.service'),
                      ('virtualbox-guest-utils', 'vboxservice.service'),
                      ('open-vm-tools', 'vmtoolsd.service')]:
        if pkg in installed:
            chroot('systemctl', 'enable', unit)
    deploy(TARGET, user, selected, keymap, installed, login_shell)
    install_dir = TARGET / 'opt/arch-personnel'
    shutil.copytree(ROOT, install_dir, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.tar.gz'), dirs_exist_ok=True)
    (install_dir / 'options-differees.json').write_text(json.dumps(deferred, ensure_ascii=False, indent=2) + '\n')
    write('usr/local/bin/arch-options', '#!/bin/sh\nexec python /opt/arch-personnel/postinstall.py "$@"\n', 0o755)
    chroot('chown', '-R', f'{user}:{user}', f'/home/{user}')
    # Aucun marqueur ne permet de sauter les contrôles de disque lors d'un autre lancement.
    for kernel in ['linux', 'linux-lts']:
        for name in [f'vmlinuz-{kernel}', f'initramfs-{kernel}.img']:
            if not (TARGET / 'boot' / name).is_file():
                raise RuntimeError(f'Image de démarrage manquante : {name}')
    chroot('findmnt', '--verify', '--tab-file', '/etc/fstab')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Vérifier les fichiers sans installation')
    args = parser.parse_args()
    verify_bundle()
    if args.check:
        print('Installateur et configurations présents. Aucune commande de disque exécutée.')
        return
    live_required()
    print('ARCH PERSONNEL — installation depuis le live, sans chiffrement. Ctrl+C annule.')
    print('Connexion réseau requise ; pour le Wi-Fi, utiliser iwctl avant de démarrer.')
    run('curl', '-fIsS', '--max-time', '20', 'https://archlinux.org')
    run('timedatectl', 'set-ntp', 'true')
    # Ces dépendances sont installées uniquement dans le live après les garde-fous.
    run('pacman', '-Sy', '--needed', '--noconfirm', 'gptfdisk', 'parted', 'btrfs-progs', 'dosfstools', 'pciutils')
    report = detect()
    if not report['supported_architecture']:
        raise RuntimeError('Architecture non prise en charge.')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    user = ask('Nom du compte', 'utilisateur', r'[a-z_][a-z0-9_-]{0,30}')
    if user in {'root', 'nobody'}:
        raise RuntimeError('Nom de compte réservé.')
    hostname = ask('Nom de la machine', 'archlinux', r'[a-z0-9][a-z0-9-]{0,61}[a-z0-9]|[a-z0-9]')
    keymap = ask('Clavier console et Hyprland : us ou fr', 'us', r'us|fr')
    locale = ask('Langue : fr_FR.UTF-8 ou en_US.UTF-8', 'fr_FR.UTF-8', r'fr_FR\.UTF-8|en_US\.UTF-8')
    timezone = ask('Fuseau horaire', 'Etc/UTC', r'[A-Za-z_+-]+/[A-Za-z0-9_+/-]+')
    zone = (Path('/usr/share/zoneinfo') / timezone).resolve()
    if not zone.is_relative_to('/usr/share/zoneinfo') or not zone.is_file():
        raise RuntimeError('Fuseau horaire inexistant.')
    rows = prepare_catalogue(json.loads((ROOT / 'catalogue/choix.json').read_text()), report)
    selected_ids = {r['id'] for r in rows if r['default'] and not r['locked']}
    if not curses.wrapper(menu, rows, selected_ids):
        print('Installation annulée.')
        return
    selected = [r for r in rows if r['id'] in selected_ids and not r['locked']]
    if any(r['id'] == 'cfg:quickshell' for r in selected) and not any(r['id'] == 'cfg:hypr' for r in selected):
        print('Ton Quickshell nécessite le profil Hyprland personnel : configuration ajoutée.')
        selected.append(next(r for r in rows if r['id'] == 'cfg:hypr'))
    login_shell = ask('Shell de connexion : bash/fish', 'fish', r'bash|fish')
    if login_shell == 'fish' and not any(r['name'] == 'fish' for r in selected):
        selected.append(next(r for r in rows if r['name'] == 'fish'))
    # L'ISO officiel fournit core/extra. Activer multilib pour les options 32 bits.
    pacman_conf = Path('/etc/pacman.conf')
    if not re.search(r'^\[multilib\]', pacman_conf.read_text(), re.M):
        with pacman_conf.open('a') as stream:
            stream.write('\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n')
        run('pacman', '-Sy')
    official, deferred = package_plan(selected, report)
    disk = choose_disk()
    mode = ask('Mode : effacer / partitions (partitions déjà préparées)', 'partitions', r'effacer|partitions')
    parts = manual_parts(disk, report['uefi']) if mode == 'partitions' else None
    print('\nCIBLE :', disk['name'], disk.get('model'), disk['size'], 'octets')
    print('EFFACEMENT COMPLET DU DISQUE' if not parts else f'FORMATAGE de {parts[0]} ; ESP {parts[1]} conservée mais fichiers de démarrage ajoutés.')
    print('Configurations :', ', '.join(r['name'] for r in selected if r['kind'] == 'configuration'))
    if 'snapper' in official:
        print('Snapper sera installé ; aucun rollback automatique de /boot n’est configuré.')
    token = f'INSTALLER {disk["name"]}' if not parts else f'FORMATER {parts[0]}'
    if input(f'Taper exactement « {token} » pour continuer : ') != token:
        print('Annulé avant toute modification du disque cible.')
        return
    revalidate(disk)
    # Vérifier le paquet au complet avant d'ouvrir la phase destructive.
    verify_bundle()
    root, esp = parts if parts else partition(disk, report['uefi'])
    mount_root(root, esp)
    run('pacstrap', '-K', TARGET, *official)
    configure(user, hostname, keymap, timezone, locale, report, root, disk, selected, deferred, login_shell)
    write('var/log/arch-personnel-installation.json', json.dumps({
        'hardware': report, 'user': user, 'hostname': hostname,
        'disk': disk['name'], 'mode': mode, 'encryption': False,
        'packages': official, 'deferred': deferred,
        'configurations': [r['id'] for r in selected if r['kind'] == 'configuration'],
    }, ensure_ascii=False, indent=2) + '\n')
    if deferred and ask('Installer maintenant les compléments AUR ? oui/non', 'oui', r'oui|non') == 'oui':
        try:
            chroot('runuser', '-u', user, '--', 'env', f'HOME=/home/{user}',
                   'python', '/opt/arch-personnel/postinstall.py')
        except subprocess.CalledProcessError:
            print('Certains compléments ont échoué ou ont été annulés ; reprendre avec arch-options après connexion.')
    print('\nInstallation terminée. Connexion après reboot :', user)
    print('Démarrer le bureau : start-desktop')
    print('Installer les options AUR après connexion : arch-options')
    print('Vérifier le système monté dans', TARGET, 'avant de redémarrer.')
    if ask('Démonter maintenant ? oui/non', 'oui', r'oui|non') == 'oui':
        run('umount', '-R', TARGET)
    print('Tu peux redémarrer avec reboot, puis retirer la clé.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'\nARRÊT : {error}\nAucune reprise automatique. Inspecter les montages avant de relancer.', file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nInterrompu. Les étapes déjà appliquées ne sont pas annulées ; aucun reformatage automatique.', file=sys.stderr)
        sys.exit(130)
