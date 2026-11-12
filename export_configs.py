#!/usr/bin/env python3
"""Créer une copie filtrée des sources ; aucun historique, compte ou état de session."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def export(home, output):
    output.mkdir(parents=True, exist_ok=False)
    entries = {}
    allowed = {'.lua', '.qml', '.js', '.json', '.sh', '.conf', '.ini', '.fish',
               '.png', '.jpg', '.jpeg', '.svg', '.frag', '.qsb', '.service', '.rules',
               '.kvconfig', '.theme', '.ttf', '.otf'}
    excluded = {'tests', 'docs', '.git', '__pycache__', 'node_modules', 'state', 'cache'}

    def include(key, source, destination, folder):
        if not source.exists():
            return
        candidates = sorted(source.rglob('*')) if source.is_dir() else [source]
        copied = False
        for path in candidates:
            relative = path.relative_to(source) if source.is_dir() else Path(source.name)
            if not path.is_file() or path.is_symlink() or excluded.intersection(relative.parts):
                continue
            if path.name.startswith(('Test', 'probe', 'check_', 'lock_test', '.')):
                continue
            # Les scripts système sans extension sont autorisés uniquement sous ces sources.
            if path.suffix not in allowed and path.name != 'qmldir' and not (not path.suffix and (path.read_bytes().startswith(b'#!') or 'pam' in relative.parts)):
                continue
            out = output / 'configs' / folder / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
            copied = True
        if copied:
            if source.is_dir():
                entry = {'source': 'configs/' + folder, 'destination': destination}
            else:
                entry = {'source': 'configs/' + folder + '/' + source.name, 'destination': destination}
            entries.setdefault(key, []).append(entry)

    for name in ['hypr', 'quickshell', 'nvim']:
        include('cfg:' + name, home / '.my-hyprland' / name, '.my-hyprland/' + name, name)
    for name in ['kitty', 'foot']:
        include('cfg:' + name, home / '.config' / name, '.config/' + name, name)
    include('cfg:fish', home / '.config/fish/config.fish', '.config/fish/config.fish', 'fish')
    for name in ['functions', 'conf.d', 'completions']:
        include('cfg:fish', home / '.config/fish' / name, '.config/fish/' + name, 'fish/' + name)
    include('cfg:starship', home / '.config/starship.toml', '.config/starship.toml', 'starship')
    # TOML autorisé explicitement pour l'invite ; aucun fichier d'authentification.
    if (home / '.config/starship.toml').is_file():
        out = output / 'configs/starship/starship.toml'
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(home / '.config/starship.toml', out)
        entries['cfg:starship'] = [{'source': 'configs/starship/starship.toml', 'destination': '.config/starship.toml'}]
    include('cfg:tmux', home / '.config/tmux/tmux.conf', '.config/tmux/tmux.conf', 'tmux')
    include('cfg:tmux', home / '.config/tmux/scripts', '.config/tmux/scripts', 'tmux/scripts')
    for name in ['gtk-3.0', 'gtk-4.0']:
        include('cfg:gtk', home / '.config' / name / 'settings.ini', '.config/' + name + '/settings.ini', name)
    for name in ['qt5ct', 'qt6ct', 'Kvantum']:
        include('cfg:qt', home / '.config' / name, '.config/' + name, name)
    include('cfg:mime', home / '.config/mimeapps.list', '.config/mimeapps.list', 'mime')
    if (home / '.config/mimeapps.list').is_file():
        out = output / 'configs/mime/mimeapps.list'
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(home / '.config/mimeapps.list', out)
        entries['cfg:mime'] = [{'source': 'configs/mime/mimeapps.list', 'destination': '.config/mimeapps.list'}]
    (output / 'entries.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n')
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Export filtré :', len(manifest), 'fichiers,', sum(p.stat().st_size for p in output.rglob('*') if p.is_file()), 'octets')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--output', type=Path, default=ROOT / 'payload')
    args = parser.parse_args()
    export(args.home, args.output)
