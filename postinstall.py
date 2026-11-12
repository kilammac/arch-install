#!/usr/bin/env python3
"""Compléments AUR, à lancer avec le compte installé : arch-options."""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

EXCLUDED_PACKAGES = frozenset({'dsearch-bin', 'flea-arch-git'})


def normalize_packages(packages):
    if not isinstance(packages, list) or not all(isinstance(p, str) and re.fullmatch(r'[a-zA-Z0-9@._+-]+', p) for p in packages):
        raise ValueError('Liste de paquets invalide.')
    return list(dict.fromkeys(p for p in packages if p not in EXCLUDED_PACKAGES))


def save_failed(failed):
    state = Path.home() / '.local/state/arch-personnel'
    state.mkdir(parents=True, exist_ok=True)
    (state / 'options-en-echec.json').write_text(json.dumps(failed, indent=2) + '\n')


def main(source=Path('/opt/arch-personnel/options-differees.json'), unattended=False):
    if os.geteuid() == 0:
        raise SystemExit('Lancer arch-options avec le compte ordinaire, sans sudo devant la commande.')
    try:
        packages = normalize_packages(json.loads(source.read_text()))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not packages:
        save_failed([])
        print('Aucune option différée.')
        return
    print('Options sélectionnées :', ', '.join(packages))
    if unattended:
        print('Installation automatique des options sélectionnées, sans saisie supplémentaire.')
        subprocess.run(['sudo', '-n', '/usr/bin/pacman', '-V'], check=True, stdin=subprocess.DEVNULL)
    else:
        print('Les PKGBUILD AUR sont des scripts communautaires ; yay proposera leur consultation.')
        subprocess.run(['sudo', '-v'], check=True)
    batch = {'stdin': subprocess.DEVNULL} if unattended else {}
    helper = shutil.which('yay')
    if not helper:
        cache = Path.home() / '.cache/arch-personnel'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='yay-', dir=cache) as directory:
            subprocess.run(['git', 'clone', 'https://aur.archlinux.org/yay.git', directory], check=True, **batch)
            pkgbuild = Path(directory) / 'PKGBUILD'
            print(pkgbuild.read_text())
            if not unattended and input('Construire et installer yay depuis ce PKGBUILD ? oui/non : ').strip() != 'oui':
                raise SystemExit('Compléments annulés.')
            subprocess.run(['makepkg', '-si', '--needed', *(['--noconfirm'] if unattended else [])],
                           cwd=directory, check=True, **batch)
        helper = shutil.which('yay')
    if not helper:
        raise SystemExit('yay non installé.')
    failed = []
    automatic = ['--noconfirm', '--answerclean', 'None', '--answerdiff', 'None',
                 '--answeredit', 'None', '--removemake', '--sudoloop=false',
                 '--sudo', '/usr/bin/sudo', '--sudoflags=-n'] if unattended else []
    for package in packages:
        result = subprocess.run([helper, '-S', '--needed', *automatic, '--', package], **batch)
        if result.returncode:
            failed.append(package)
    save_failed(failed)
    print('Options en échec :', ', '.join(failed) or 'aucune')
    if any(p.startswith('nvidia-580xx') for p in packages) and not failed:
        subprocess.run(['sudo', *(['-n'] if unattended else []), '/usr/bin/mkinitcpio', '-P'], check=True, **batch)
        print('Pilote NVIDIA installé : redémarrer.')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unattended', action='store_true', help='Installation sans questions (autorisation sudo requise)')
    main(unattended=parser.parse_args().unattended)
