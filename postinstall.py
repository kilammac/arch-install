#!/usr/bin/env python3
"""Compléments AUR, à lancer avec le compte installé : arch-options."""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    if os.geteuid() == 0:
        raise SystemExit('Lancer arch-options avec le compte ordinaire, sans sudo devant la commande.')
    source = Path('/opt/arch-personnel/options-differees.json')
    packages = json.loads(source.read_text())
    if not isinstance(packages, list) or not all(isinstance(p, str) and re.fullmatch(r'[a-zA-Z0-9@._+-]+', p) for p in packages):
        raise SystemExit('Liste de paquets invalide.')
    if not packages:
        print('Aucune option différée.')
        return
    print('Options sélectionnées :', ', '.join(packages))
    print('Les PKGBUILD AUR sont des scripts communautaires ; yay proposera leur consultation.')
    subprocess.run(['sudo', '-v'], check=True)
    helper = shutil.which('yay')
    if not helper:
        cache = Path.home() / '.cache/arch-personnel'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='yay-', dir=cache) as directory:
            subprocess.run(['git', 'clone', 'https://aur.archlinux.org/yay.git', directory], check=True)
            pkgbuild = Path(directory) / 'PKGBUILD'
            print(pkgbuild.read_text())
            if input('Construire et installer yay depuis ce PKGBUILD ? oui/non : ').strip() != 'oui':
                raise SystemExit('Compléments annulés.')
            subprocess.run(['makepkg', '-si', '--needed'], cwd=directory, check=True)
        helper = shutil.which('yay')
    if not helper:
        raise SystemExit('yay non installé.')
    failed = []
    for package in packages:
        result = subprocess.run([helper, '-S', '--needed', package])
        if result.returncode:
            failed.append(package)
    state = Path.home() / '.local/state/arch-personnel'
    state.mkdir(parents=True, exist_ok=True)
    (state / 'options-en-echec.json').write_text(json.dumps(failed, indent=2) + '\n')
    print('Options en échec :', ', '.join(failed) or 'aucune')
    if any(p.startswith('nvidia-580xx') for p in packages) and not failed:
        subprocess.run(['sudo', 'mkinitcpio', '-P'], check=True)
        print('Pilote NVIDIA installé : redémarrer.')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
