#!/usr/bin/env python3
"""Installateur live : étapes explicites, sans reprise du partitionnement."""
import argparse
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
from deploy import deploy, config_packages
from tui import UI
from session_state import Session, RELATIVE
from recovery import SUBVOLS, disk_identity, uuid_of, resolve_layout, mount_existing, discover
import snapshots

ROOT = Path(__file__).resolve().parent
TARGET = Path('/mnt/arch-personnel')


def run(*args, capture=False, interactive=False):
    return UI.command([str(a) for a in args], capture=capture, interactive=interactive)


def ask(prompt, default='', pattern=None):
    if pattern == r'oui|non':
        return UI.choose(prompt, [('Oui', 'oui'), ('Non', 'non')], default=default)
    while True:
        value = UI.input(prompt, default)
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


def live_required(check_target=True):
    if os.geteuid() != 0 or not Path('/run/archiso').is_dir():
        raise RuntimeError('Refus : utiliser le live ISO Arch comme root.')
    if os.uname().machine != 'x86_64':
        raise RuntimeError('Seul Arch x86_64 est pris en charge.')
    if check_target and TARGET.exists() and any(TARGET.iterdir()):
        raise RuntimeError(f'{TARGET} non vide : inspecter/démonter la tentative précédente avant de continuer.')
    if check_target and subprocess.run(['mountpoint', '-q', str(TARGET)]).returncode == 0:
        raise RuntimeError('Cible déjà montée ; aucune reprise automatique du formatage.')
    # L'ISO Arch ne démarre normalement pas sous Secure Boot, mais vérifier aussi efivarfs.
    for variable in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        data = variable.read_bytes()
        if len(data) > 4 and data[4] == 1:
            raise RuntimeError('Désactiver Secure Boot pour cette installation.')


def prepare_live_pacman(path=Path('/etc/pacman.conf')):
    original = path.read_text()
    text = re.sub(r'(?m)^\s*#?\s*ParallelDownloads\s*=.*$', 'ParallelDownloads = 5', original)
    if not re.search(r'^ParallelDownloads\s*=', text, re.M):
        text = re.sub(r'(?m)^\[options\]\s*$', '[options]\nParallelDownloads = 5', text, count=1)
    if not re.search(r'^\[multilib\]', text, re.M):
        text += '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n'
    if text != original:
        path.write_text(text)
        return True
    return False


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
    path = UI.choose('Installer sur quel disque ?', [(f'{d["name"]} · {d.get("model") or "Disque"} · {int(d["size"])/1024**3:.1f} Gio', d['name']) for d in disks])
    return next(d for d in disks if d['name'] == path)


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


def package_plan(selected, report, boot='systemd-boot', snapshot_mode='none'):
    fixed = set('base base-devel linux linux-headers linux-lts linux-lts-headers linux-firmware btrfs-progs sudo networkmanager nano python git curl rsync pciutils usbutils dosfstools zram-generator'.split())
    hw, extra = graphics(report)
    # Compatibilité avec d'anciens aperçus matériels et anciennes réponses.
    hw = {'mesa' if p == 'libva-mesa-driver' else p for p in hw}
    requested = {r['name'] for r in selected if r['kind'] == 'paquet'}
    required = fixed | config_packages(selected) | hw
    required |= snapshots.packages(snapshot_mode)
    if report['form_factor'] == 'laptop' and report['virtualization'] == 'none':
        required.add('power-profiles-daemon')
    # Empêcher la transplantation de réglages d'amorçage/dépôts de l'ancien système.
    requested -= {'update-grub', 'chaotic-keyring', 'chaotic-mirrorlist', 'snapper-rollback', 'snapper', 'snap-pac'}
    if 'steam' in requested:
        if any(g['vendor_id'] == '0x1002' for g in report['gpus']):
            required.update(['lib32-mesa', 'lib32-vulkan-radeon'])
        if any(g['vendor_id'] == '0x8086' for g in report['gpus']):
            required.update(['lib32-mesa', 'lib32-vulkan-intel'])
        if 'nvidia-utils' in hw:
            required.add('lib32-nvidia-utils')
    if report['uefi']:
        required.add('efibootmgr')
    if boot == 'grub' or not report['uefi']:
        required.add('grub')
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
    subvols = SUBVOLS
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
    return run('arch-chroot', TARGET, *args, capture=capture,
               interactive=bool(args and args[0] in {'passwd', 'runuser'}))


def options_runtime_permissions(directory):
    """copytree conserve le 700 de mktemp : ouvrir uniquement les fichiers publics requis."""
    files = [directory / 'postinstall.py', directory / 'options-differees.json']
    if directory.is_symlink() or not directory.is_dir() or any(p.is_symlink() or not p.is_file() for p in files):
        raise RuntimeError('Compléments : fichiers installés absents ou liens inattendus dans /opt/arch-personnel.')
    directory.chmod(0o755)
    for path in files:
        path.chmod(0o644)


def prepare_options_runtime(user):
    directory = TARGET / 'opt/arch-personnel'
    options_runtime_permissions(directory)
    chroot('chown', 'root:root', '/opt/arch-personnel', '/opt/arch-personnel/postinstall.py',
           '/opt/arch-personnel/options-differees.json')
    # Contrôle réel comme utilisateur, sans exécuter le programme ni construire de paquet.
    probe = ('from pathlib import Path; import ast,json; '
             'ast.parse(Path("/opt/arch-personnel/postinstall.py").read_text()); '
             'json.loads(Path("/opt/arch-personnel/options-differees.json").read_text())')
    chroot('runuser', '-u', user, '--', 'env', f'HOME=/home/{user}', f'USER={user}',
           f'LOGNAME={user}', 'python', '-I', '-c', probe)


def run_options(user):
    prepare_options_runtime(user)
    chroot('runuser', '-u', user, '--', 'env', f'HOME=/home/{user}', f'USER={user}',
           f'LOGNAME={user}', 'python', '-I', '/opt/arch-personnel/postinstall.py')


def execute_step(session, name, label, action):
    if session and session.done(name):
        UI.progress(label + ' · déjà terminé')
        return
    return UI.step(label, lambda: session.perform(name, action) if session else action())


def configure(user, hostname, keymap, timezone, locale, report, root, disk, selected, deferred,
              login_shell='bash', boot='systemd-boot', session=None, snapshot_mode='none'):
    def locale_setup():
        write('etc/fstab', run('genfstab', '-U', TARGET, capture=True) + '\n')
        write('etc/hostname', hostname + '\n')
        write('etc/hosts', f'127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {hostname}.localdomain {hostname}\n')
        write('etc/locale.gen', 'en_US.UTF-8 UTF-8\nfr_FR.UTF-8 UTF-8\n')
        write('etc/locale.conf', f'LANG={locale}\n')
        write('etc/vconsole.conf', f'KEYMAP={keymap}\n')
        chroot('ln', '-sf', '/usr/share/zoneinfo/' + timezone, '/etc/localtime')
        chroot('hwclock', '--systohc')
        chroot('locale-gen')
        write('etc/systemd/zram-generator.conf', '[zram0]\nzram-size = min(ram / 2, 8192)\ncompression-algorithm = zstd\n')
    execute_step(session, 'locale', 'Langue, heure et montages', locale_setup)

    def account():
        entry = next((line.split(':') for line in (TARGET / 'etc/passwd').read_text().splitlines()
                      if line.split(':', 1)[0] == user), None)
        shell = '/usr/bin/fish' if login_shell == 'fish' else '/bin/bash'
        if entry:
            if int(entry[2]) < 1000 or entry[5] != '/home/' + user:
                raise RuntimeError('Un compte système ou un autre home occupe le nom choisi.')
            chroot('usermod', '-aG', 'wheel', '-s', shell, user)
        else:
            chroot('useradd', '-m', '-G', 'wheel', '-s', shell, user)
        write('etc/sudoers.d/10-wheel', '%wheel ALL=(ALL:ALL) ALL\n', 0o440)
        chroot('visudo', '-cf', '/etc/sudoers')
    execute_step(session, 'account', 'Compte et sudo', account)

    def passwords():
        print('Définis le mot de passe du compte ; il ne sera jamais enregistré dans l’état de reprise.')
        chroot('passwd', user)
        chroot('usermod', '-L', 'root')
    execute_step(session, 'password-set', 'Mot de passe du compte', passwords)

    def boot_setup():
        write('etc/mkinitcpio.conf.d/10-personnel.conf', 'HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck)\n')
        chroot('mkinitcpio', '-P')
        if report['uefi'] and boot == 'systemd-boot':
            try:
                chroot('bootctl', '--esp-path=/boot', 'install')
            except subprocess.CalledProcessError:
                chroot('bootctl', '--esp-path=/boot', '--no-variables', 'install')
            uuid = uuid_of(root, run)
            write('boot/loader/loader.conf', 'default arch.conf\ntimeout 5\nconsole-mode keep\neditor no\n')
            for kernel, title in [('linux', 'Arch Linux'), ('linux-lts', 'Arch Linux LTS')]:
                filename = 'arch.conf' if kernel == 'linux' else 'arch-lts.conf'
                write('boot/loader/entries/' + filename,
                      f'title {title}\nlinux /vmlinuz-{kernel}\ninitrd /initramfs-{kernel}.img\noptions root=UUID={uuid} rootflags=subvol=@ rw\n')
        else:
            if report['uefi']:
                chroot('grub-install', '--target=x86_64-efi', '--efi-directory=/boot', '--bootloader-id=Arch')
            else:
                chroot('grub-install', '--target=i386-pc', disk['name'])
            chroot('grub-mkconfig', '-o', '/boot/grub/grub.cfg')
    execute_step(session, 'boot', 'Noyaux et chargeur de démarrage', boot_setup)

    def services():
        installed = set(chroot('pacman', '-Qq', capture=True).splitlines())
        chroot('systemctl', 'enable', 'NetworkManager.service', 'systemd-timesyncd.service')
        for pkg, unit in [('bluez', 'bluetooth.service'), ('cups', 'cups.service'),
                          ('power-profiles-daemon', 'power-profiles-daemon.service'),
                          ('qemu-guest-agent', 'qemu-guest-agent.service'),
                          ('virtualbox-guest-utils', 'vboxservice.service'), ('open-vm-tools', 'vmtoolsd.service')]:
            if pkg in installed:
                chroot('systemctl', 'enable', unit)
    execute_step(session, 'services', 'Services du système', services)

    def desktop():
        installed = set(chroot('pacman', '-Qq', capture=True).splitlines())
        deploy(TARGET, user, selected, keymap, installed, login_shell)
        install_dir = TARGET / 'opt/arch-personnel'
        shutil.copytree(ROOT, install_dir, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.tar.gz'), dirs_exist_ok=True)
        (install_dir / 'options-differees.json').write_text(json.dumps(deferred, ensure_ascii=False, indent=2) + '\n')
        write('usr/local/bin/arch-options', '#!/bin/sh\nexec python /opt/arch-personnel/postinstall.py "$@"\n', 0o755)
        prepare_options_runtime(user)
        chroot('chown', '-R', f'{user}:{user}', f'/home/{user}')
    execute_step(session, 'deploy', 'Déployer ta configuration et ton bureau', desktop)
    if snapshot_mode != 'none':
        execute_step(session, 'snapshots', 'Configurer Snapper', lambda: snapshots.configure(TARGET, snapshot_mode, chroot))


def verify_target():
    for kernel in ['linux', 'linux-lts']:
        for name in [f'vmlinuz-{kernel}', f'initramfs-{kernel}.img']:
            image = TARGET / 'boot' / name
            if not image.is_file() or image.stat().st_size == 0:
                raise RuntimeError(f'Image de démarrage manquante : {name}')
    chroot('findmnt', '--verify', '--tab-file', '/etc/fstab')


def validate_settings(settings, report):
    patterns = {'user': r'[a-z_][a-z0-9_-]{0,30}',
                'hostname': r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',
                'timezone': r'[A-Za-z_+-]+/[A-Za-z0-9_+/-]+'}
    for key, pattern in patterns.items():
        if not isinstance(settings.get(key), str) or not re.fullmatch(pattern, settings[key]):
            raise ValueError('Réponse enregistrée invalide : ' + key)
    if settings['user'] in {'root', 'nobody'}:
        raise ValueError('Compte réservé dans les réponses.')
    for key, allowed in {'keymap': {'us', 'fr'}, 'locale': {'fr_FR.UTF-8', 'en_US.UTF-8'},
                         'login_shell': {'bash', 'fish'}, 'boot': {'grub', 'systemd-boot'},
                         'snapshot_mode': snapshots.MODES}.items():
        if settings.get(key) not in allowed:
            raise ValueError('Choix enregistré invalide : ' + key)
    if not isinstance(settings.get('uefi'), bool) or settings['uefi'] != report['uefi']:
        raise RuntimeError('Le mode de démarrage a changé : reprendre avec le même mode UEFI/BIOS.')
    zone = (Path('/usr/share/zoneinfo') / settings['timezone']).resolve()
    if not zone.is_relative_to('/usr/share/zoneinfo') or not zone.is_file():
        raise ValueError('Fuseau enregistré invalide.')
    digest = hashlib.sha256((ROOT / 'payload/manifest.json').read_bytes()).hexdigest()
    if settings.get('payload_digest') != digest:
        raise RuntimeError('Les configurations ont changé : reprendre avec le même paquet de configuration.')
    rows = prepare_catalogue(json.loads((ROOT / 'catalogue/choix.json').read_text()), report)
    ids = settings.get('selected_ids')
    known = {r['id'] for r in rows if not r['locked']}
    if not isinstance(ids, list) or not all(isinstance(item, str) and item in known for item in ids):
        raise ValueError('Liste de logiciels/configurations enregistrée invalide.')
    return [r for r in rows if r['id'] in ids]


def progress_steps(snapshot_mode, deferred):
    names = ['filesystem', 'base', 'locale', 'account', 'password-set', 'boot', 'services', 'deploy']
    if snapshot_mode != 'none':
        names.append('snapshots')
    if deferred:
        names.append('options')
    if snapshot_mode != 'none':
        names.append('initial-snapshot')
    return names + ['verify']


def backup_state_path(directory):
    directory = Path(directory).resolve()
    if directory.is_relative_to(ROOT) or directory.is_relative_to(TARGET):
        raise ValueError('La copie externe doit rester hors du dépôt et hors de la cible.')
    parent = directory
    while not parent.exists():
        parent = parent.parent
    kind = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(parent)], text=True).strip()
    if kind in {'tmpfs', 'ramfs', 'overlay', 'squashfs', 'iso9660'} or not kind:
        raise ValueError('--state-dir doit désigner un support persistant monté, par exemple une clé USB.')
    options = subprocess.check_output(['findmnt', '-n', '-o', 'OPTIONS', '-T', str(parent)], text=True).strip()
    if 'ro' in options.split(','):
        raise ValueError('La copie externe nécessite un support monté en lecture-écriture.')
    return directory / 'state.json'


def prepare_existing_session(session, report, fresh_log=False):
    layout = session.data.get('layout')
    if not layout:
        if session.data.get('in_progress') == 'filesystem':
            raise RuntimeError('Arrêt pendant le partitionnement/formatage. Reprise automatique refusée : inspecter les partitions ; ne pas relancer un effacement pour reprendre.')
        if session.data['completed'] or session.data.get('in_progress'):
            raise RuntimeError('État incomplet : étapes présentes sans identité de partitions. Aucun formatage autorisé.')
        return None
    disk, root, esp = resolve_layout(layout, blocks(), TARGET, run)
    mount_existing(TARGET, root, esp, layout, run)
    old_log = (TARGET / RELATIVE).parent / 'install.log'
    if fresh_log and old_log.is_file() and UI.log:
        current = UI.log.read_text()
        UI.log.write_text(old_log.read_text() + '\n--- REPRISE DEPUIS LE LIVE ---\n' + current)
    session.attach(TARGET / RELATIVE)
    if not session.done('filesystem'):
        session.data['completed'].append('filesystem')
        session.data['in_progress'] = None
        session.save()
    if session.done('base'):
        installed = set(chroot('pacman', '-Qq', capture=True).splitlines())
        missing = set(session.data.get('packages', ['base', 'linux', 'linux-lts'])) - installed
        if missing:
            raise RuntimeError('État de base incohérent : paquets manquants : ' + ', '.join(sorted(missing)))
    if session.done('deploy'):
        prepare_options_runtime(session.data['settings']['user'])
    return disk, root, esp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Vérifier les fichiers sans installation')
    parser.add_argument('--preview', '--dry-run', action='store_true', help='Essayer les menus sans installation ni écriture')
    parser.add_argument('--state-dir', type=Path, help='Copie supplémentaire de reprise sur un support persistant monté')
    parser.add_argument('--resume', type=Path, help='Charger un state.json de reprise (aucun formatage)')
    args = parser.parse_args()
    verify_bundle()
    if args.check:
        print('Installateur et configurations présents. Aucune commande de disque exécutée.')
        return
    if args.preview:
        UI.banner('APERÇU · aucun paquet installé · aucun disque modifié')
        UI.header(1, 'Ton système')
        questionnaire(detect())
        UI.header(2, 'Disque et résumé — exemple de VM')
        UI.box('/dev/vda · disque EXEMPLE\nBtrfs · Linux + LTS\nAucune commande d’installation exécutée.')
        UI.set_steps(3)
        for label in ['EXEMPLE : partitions', 'EXEMPLE : logiciels', 'EXEMPLE : configuration']:
            UI.step(label, lambda: None)
        return
    live_required(check_target=False)
    logdir = Path('/run/arch-personnel')
    logdir.mkdir(mode=0o700, exist_ok=True)
    UI.log = logdir / 'install.log'
    fresh_log = not UI.log.exists() or UI.log.stat().st_size == 0
    UI.log.touch(mode=0o600)
    runtime = logdir / 'state.json'
    backup = backup_state_path(args.state_dir) if args.state_dir else None
    if args.resume and not args.resume.is_file():
        raise ValueError('Le fichier de reprise demandé est introuvable.')
    candidates = discover(runtime, TARGET, args.resume or (backup if backup and backup.is_file() else None))
    session = None
    UI.banner()
    if candidates:
        if len(candidates) == 1:
            origin, data = candidates[0]
        else:
            index = int(UI.choose('Quelle installation retrouver ?', [
                (f'{origin} · {data["settings"].get("hostname", "installation")} · {"terminée" if data["finished"] else "à reprendre"}', str(n))
                for n, (origin, data) in enumerate(candidates)]))
            origin, data = candidates[index]
        label = 'Reprendre sans reformater' if data.get('layout') else 'Retrouver les réponses (préparation du disque à vérifier et confirmer)'
        choices = [(label, 'resume')] if not data['finished'] else []
        choices += [('Quitter', 'quit'), ('Préparer une nouvelle installation', 'new')]
        choice = UI.choose('État retrouvé : ' + origin, choices)
        if choice == 'quit':
            return
        if choice == 'resume':
            session = Session(data, [runtime], UI.log)
    elif args.resume:
        raise ValueError('Aucun état de reprise valide.')
    if not session:
        live_required()
    if backup:
        if not session:
            print('Copie de reprise externe :', backup)
        elif backup not in session.paths:
            session.paths.append(backup)
    UI.header(0, 'Vérifications du live')
    while True:
        try:
            run('curl', '-fsS', '--max-time', '20', '-o', '/dev/null', 'https://archlinux.org')
            break
        except subprocess.CalledProcessError:
            action = UI.choose('Pas de connexion Internet', [('Configurer le Wi-Fi avec iwctl', 'wifi'), ('Réessayer', 'retry'), ('Annuler', 'cancel')])
            if action == 'wifi':
                run('iwctl', interactive=True)
            elif action == 'cancel':
                raise RuntimeError('Connexion Internet non disponible.')
    run('timedatectl', 'set-ntp', 'true')
    prepare_live_pacman()
    run('pacman', '-Sy', '--needed', '--noconfirm', 'gum', 'gptfdisk', 'parted', 'btrfs-progs', 'dosfstools', 'pciutils')
    report = detect()
    if not report['supported_architecture']:
        raise RuntimeError('Architecture non prise en charge.')
    vendors = {'0x1002': 'AMD Radeon', '0x8086': 'Intel', '0x10de': 'NVIDIA', '0x1af4': 'VirtIO', '0x15ad': 'VMware', '0x1234': 'QEMU'}
    cards = '\n'.join(f'GPU : {vendors.get(g["vendor_id"], g["vendor_id"])} · {g["pci"]}' for g in report['gpus'])
    UI.box(f'{report["manufacturer"] or "Machine"} · {report["model"] or "modèle inconnu"}\nCPU : {", ".join(report["cpu_vendors"])}\n{cards}\nDémarrage : {"UEFI" if report["uefi"] else "BIOS"}')
    UI.header(1, 'Ton système et tes logiciels')
    if session:
        settings = session.data['settings']
        selected = validate_settings(settings, report)
    else:
        user, hostname, keymap, locale, timezone, selected, login_shell, boot, snapshot_mode = questionnaire(report)
        settings = dict(user=user, hostname=hostname, keymap=keymap, locale=locale,
                        timezone=timezone, login_shell=login_shell, boot=boot, snapshot_mode=snapshot_mode,
                        selected_ids=[r['id'] for r in selected], uefi=report['uefi'],
                        payload_digest=hashlib.sha256((ROOT / 'payload/manifest.json').read_bytes()).hexdigest())
        session = Session.create(settings, runtime, UI.log)
        if backup:
            session.attach(backup)
    user, hostname, keymap, locale, timezone = (settings[key] for key in ['user', 'hostname', 'keymap', 'locale', 'timezone'])
    login_shell, boot, snapshot_mode = (settings[key] for key in ['login_shell', 'boot', 'snapshot_mode'])
    official, deferred = package_plan(selected, report, boot, snapshot_mode)
    session.data['packages'] = official
    session.data['deferred'] = deferred
    session.save()
    UI.header(2, 'Disque et confirmation')
    existing = prepare_existing_session(session, report, fresh_log)
    if existing:
        disk, root, esp = existing
        mode = session.data['mode']
        UI.box(f'Reprise sur {disk["name"]}\nRacine UUID={session.data["layout"]["root_uuid"]}\n{len(session.data["completed"])} étapes déjà terminées\nAUCUN PARTITIONNEMENT NI FORMATAGE')
    else:
        disk = choose_disk()
        options = [('Effacer le disque et créer les partitions automatiquement', 'effacer')]
        if report['uefi']:
            options.append(('Utiliser des partitions déjà préparées (racine formatée)', 'partitions'))
        mode = UI.choose('Comment installer Arch ?', options)
        parts = manual_parts(disk, report['uefi']) if mode == 'partitions' else None
        UI.box(f'Compte : {user} · machine : {hostname}\nShell : {login_shell} · chargeur : {boot}\nSnapshots : {snapshot_mode}\nCible : {disk["name"]} · {int(disk["size"])/1024**3:.1f} Gio\n' +
               ('EFFACEMENT COMPLET DU DISQUE' if not parts else f'FORMATAGE : {parts[0]} · ESP conservée : {parts[1]}') +
               f'\n{len(official)} paquets officiels · {len(deferred)} compléments\nSystème non chiffré')
        if not backup:
            print('État durable sur la cible dès les premiers montages. Pour protéger aussi une coupure pendant le partitionnement, utiliser --state-dir sur une clé USB.')
        token = f'INSTALLER {disk["name"]}' if not parts else f'FORMATER {parts[0]}'
        if UI.input(f'Confirmation : taper exactement {token}') != token:
            return
        revalidate(disk)
        session.data['mode'] = mode
        session.save()
        def initialize():
            created_root, created_esp = parts if parts else partition(disk, report['uefi'])
            mount_root(created_root, created_esp)
            current = next(d for d in blocks() if d['name'] == disk['name'])
            session.data['layout'] = {'root_uuid': uuid_of(created_root, run),
                'esp_uuid': uuid_of(created_esp, run) if created_esp else None,
                'disk_identity': disk_identity(current)}
            session.attach(TARGET / RELATIVE)
            return created_root, created_esp
        names = progress_steps(snapshot_mode, deferred)
        UI.set_steps(len(names), len(set(names) & set(session.data['completed'])))
        root, esp = execute_step(session, 'filesystem', 'Partitions et système de fichiers', initialize)
    names = progress_steps(snapshot_mode, deferred)
    UI.set_steps(len(names), len(set(names) & set(session.data['completed'])))
    UI.header(3, 'Installation du système de base et des logiciels')
    execute_step(session, 'base', 'Installer les paquets', lambda: run('pacstrap', '-K', TARGET, *official))
    UI.header(4, 'Compte, démarrage et configuration du système')
    configure(user, hostname, keymap, timezone, locale, report, root, disk, selected, deferred,
              login_shell, boot, session, snapshot_mode)
    UI.header(5, 'Ton bureau, snapshots et compléments')
    if deferred:
        def options():
            if ask('Installer maintenant les compléments AUR ? oui/non', 'oui', r'oui|non') == 'non':
                return
            try:
                run_options(user)
            except subprocess.CalledProcessError:
                if UI.choose('Compléments en échec', [('Arrêter et conserver la reprise', 'abort'), ('Reporter à arch-options après démarrage', 'later')]) == 'abort':
                    raise RuntimeError('Compléments interrompus ; état de reprise conservé.')
        execute_step(session, 'options', 'Logiciels supplémentaires AUR', options)
    if snapshot_mode != 'none':
        execute_step(session, 'initial-snapshot', 'Créer le snapshot initial', lambda: snapshots.initial(chroot))
    if session.done('verify'):
        verify_target()
    execute_step(session, 'verify', 'Vérifier les images et les montages', verify_target)
    write('var/log/arch-personnel-installation.json', json.dumps({
        'hardware': report, 'user': user, 'hostname': hostname, 'disk': disk['name'],
        'mode': mode, 'encryption': False, 'snapshots': snapshot_mode,
        'packages': official, 'deferred': deferred, 'configurations': settings['selected_ids'],
    }, ensure_ascii=False, indent=2) + '\n')
    session.data['finished'] = True
    session.save()
    UI.header(6, 'Installation terminée')
    UI.progress('Installation terminée')
    shutil.copy2(UI.log, TARGET / 'var/log/arch-personnel-install.log')
    UI.box(f'Connexion : {user}\nBureau : start-desktop · compléments : arch-options\nÉtat durable : /{RELATIVE}\nJournal : /var/log/arch-personnel-install.log')
    if ask('Démonter et redémarrer maintenant ? oui/non', 'non', r'oui|non') == 'oui':
        run('umount', '-R', TARGET)
        run('reboot')
    else:
        print('Cible montée dans', TARGET, '· démonter avant de redémarrer.')


def questionnaire(report):
    user = ask('Nom du compte', 'utilisateur', r'[a-z_][a-z0-9_-]{0,30}')
    if user in {'root', 'nobody'}:
        raise RuntimeError('Nom de compte réservé.')
    hostname = ask('Nom de la machine', 'archlinux', r'[a-z0-9][a-z0-9-]{0,61}[a-z0-9]|[a-z0-9]')
    keymap = UI.choose('Clavier de la console et du bureau', [('US — QWERTY', 'us'), ('FR — AZERTY', 'fr')], default='us')
    locale = UI.choose('Langue du système', [('Français', 'fr_FR.UTF-8'), ('English', 'en_US.UTF-8')], default='fr_FR.UTF-8')
    timezone = ask('Fuseau horaire', 'Etc/UTC', r'[A-Za-z_+-]+/[A-Za-z0-9_+/-]+')
    zone = (Path('/usr/share/zoneinfo') / timezone).resolve()
    if not zone.is_relative_to('/usr/share/zoneinfo') or not zone.is_file():
        raise RuntimeError('Fuseau horaire inexistant.')
    rows = prepare_catalogue(json.loads((ROOT / 'catalogue/choix.json').read_text()), report)
    selected = UI.selections(rows)
    if any(r['id'] == 'cfg:quickshell' for r in selected) and not any(r['id'] == 'cfg:hypr' for r in selected):
        print('Ton Quickshell nécessite le profil Hyprland personnel : configuration ajoutée.')
        selected.append(next(r for r in rows if r['id'] == 'cfg:hypr'))
    login_shell = UI.choose('Shell de connexion', [('Fish', 'fish'), ('Bash', 'bash')], default='fish')
    if login_shell == 'fish' and not any(r['name'] == 'fish' for r in selected):
        selected.append(next(r for r in rows if r['name'] == 'fish'))
    boot = UI.choose('Chargeur de démarrage', [('systemd-boot (conseillé)', 'systemd-boot'), ('GRUB', 'grub')]) if report['uefi'] else 'grub'
    snapshot_mode = UI.choose('Snapshots Btrfs avec Snapper', [('Aucun snapshot', 'none'), ('Manuels et snapshot initial', 'manual'), ('Automatiques : avant/après pacman et chronologie', 'auto')], default='none')
    if snapshot_mode != 'none':
        UI.box('Snapshots du système uniquement ; /home et /boot sur ESP ne sont pas couverts.\nPas de démarrage automatique depuis un snapshot.')
    return user, hostname, keymap, locale, timezone, selected, login_shell, boot, snapshot_mode


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        message = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            message = f'La commande {error.cmd[0]} a échoué (code {error.returncode}).'
        print(f'\nARRÊT : {message}\nAucune reprise automatique. Inspecter les montages avant de relancer.', file=sys.stderr)
        if UI.log:
            print(f'Journal complet : {UI.log}', file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nInterrompu. Les étapes déjà appliquées ne sont pas annulées ; aucun reformatage automatique.', file=sys.stderr)
        sys.exit(130)
