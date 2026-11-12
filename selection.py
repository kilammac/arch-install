#!/usr/bin/env python3
"""Sélecteur de logiciels et configurations, également appelé par installer.py."""
import argparse
import curses
import json
from pathlib import Path
from hardware import detect, prepare_catalogue

ROOT = Path(__file__).resolve().parent


def make_plan(rows, selected, hardware=None):
    hardware = hardware if hardware is not None else detect()
    chosen = [r for r in rows if r['id'] in selected and not r['locked']]
    return {
        'schema': 2,
        'status': 'selection-a-revalider-dans-le-live',
        'target': {'profile': 'auto', 'disk': None,
                   'partition_mode': None, 'encryption': False},
        'hardware_preview': hardware,
        'hardware_policy': 'Recalcul obligatoire depuis le live cible ; aucun disque choisi automatiquement.',
        'hardware_packages_preview': hardware['packages_suggested'],
        'selected_ids': [r['id'] for r in chosen],
        'packages': [r['name'] for r in chosen if r['kind'] == 'paquet'],
        'configurations': [r for r in chosen if r['kind'] == 'configuration'],
        'pending': ['Lancer install.sh dans le live pour revalider le matériel et choisir le disque'],
    }


def save_plan(path, plan):
    # Refus d'écraser des fichiers existants, y compris les liens symboliques.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def menu(screen, rows, selected):
    curses.curs_set(0)
    screen.keypad(True)
    tabs = ['Tout', 'paquet', 'configuration']
    tab, pos, search = 0, 0, ''
    while True:
        visible = [r for r in rows
                   if (tab == 0 or r['kind'] == tabs[tab])
                   and search.casefold() in (r['name'] + ' ' + r['group']).casefold()]
        pos = max(0, min(pos, len(visible) - 1))
        height, width = screen.getmaxyx()
        screen.erase()

        def line(y, text, attr=0):
            if 0 <= y < height - 1 and width > 1:
                screen.addnstr(y, 0, text, width - 1, attr)

        line(0, 'ARCH PERSONNEL — logiciels et configuration — sans chiffrement', curses.A_BOLD)
        line(1, f'Vue : {tabs[tab]} | {len(selected)} choix | Filtre : {search}')
        line(2, 'Flèches/j/k : déplacer | Espace : cocher | Tab : vue | / : filtre')
        line(3, 's : valider les choix | q : annuler | [!] : géré automatiquement / exclu')
        page = max(1, height - 9)
        start = (pos // page) * page
        for idx in range(start, min(start + page, len(visible))):
            r = visible[idx]
            mark = '!' if r['locked'] else ('x' if r['id'] in selected else ' ')
            label = f'[{mark}] {r["group"]} / {r["name"]}'
            line(5 + idx - start, label, curses.A_REVERSE if idx == pos else 0)
        if visible:
            line(height - 3, visible[pos]['note'])
        screen.refresh()
        key = screen.getch()
        if key in (ord('q'), 27):
            return False
        if key == ord('s'):
            return True
        if key in (curses.KEY_DOWN, ord('j')):
            pos = min(pos + 1, len(visible) - 1)
        elif key in (curses.KEY_UP, ord('k')):
            pos = max(0, pos - 1)
        elif key == curses.KEY_NPAGE:
            pos = min(pos + page, len(visible) - 1)
        elif key == curses.KEY_PPAGE:
            pos = max(0, pos - page)
        elif key == 9:
            tab, pos = (tab + 1) % len(tabs), 0
        elif key == ord(' ') and visible:
            r = visible[pos]
            if not r['locked']:
                if r['id'] in selected:
                    selected.remove(r['id'])
                else:
                    selected.add(r['id'])
        elif key == ord('/'):
            line(height - 2, 'Recherche (vide = tout) : ')
            screen.refresh()
            curses.echo()
            try:
                search = screen.getstr(height - 2, min(25, width - 2),
                                       max(1, width - 27)).decode('utf-8', errors='replace')
            finally:
                curses.noecho()
            pos = 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--defaults', action='store_true', help='Préparer les choix suggérés sans menu')
    parser.add_argument('--output', type=Path, help='Exporter dans un nouveau fichier JSON')
    parser.add_argument('--answers', type=Path, help='Recharger selected_ids depuis un export JSON')
    args = parser.parse_args()
    rows = json.loads((ROOT / 'catalogue/choix.json').read_text())
    hardware = detect()
    rows = prepare_catalogue(rows, hardware)
    selected = {r['id'] for r in rows if r['default'] and not r['locked']}
    if args.answers:
        loaded = json.loads(args.answers.read_text())['selected_ids']
        known = {r['id'] for r in rows}
        allowed = {r['id'] for r in rows if not r['locked']}
        if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
            parser.error('selected_ids doit être une liste de textes')
        if set(loaded) - known:
            parser.error('Identifiants inconnus')
        # Une sélection voyage entre machines ; les anciens pilotes sont recalculés.
        selected = set(loaded) & allowed
    if not args.defaults and not curses.wrapper(menu, rows, selected):
        print('Fermé sans export.')
        return
    plan = make_plan(rows, selected, hardware)
    if args.output:
        try:
            save_plan(args.output, plan)
        except OSError as error:
            parser.exit(1, f'Export impossible : {error}\n')
        print(f'Proposition enregistrée : {args.output}')
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
