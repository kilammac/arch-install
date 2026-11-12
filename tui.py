"""Parcours Gum : familles, choix fins, résumé et étapes, inspiré de bboysidou."""
import shutil
import subprocess
import sys
from pathlib import Path

GROUPS = {
    '01-base': 'Socle et outils système', '02-bureau-hyprland': 'Bureau Hyprland et audio',
    '03-terminal-editeurs': 'Terminaux et éditeurs', '04-developpement': 'Développement',
    '05-android': 'Android', '06-conteneurs-vm': 'Conteneurs et virtualisation',
    '07-navigateurs': 'Navigateurs', '08-media-creation': 'Multimédia et création',
    '09-bureautique-ocr': 'Bureautique et OCR', '10-peripheriques-reseau': 'Périphériques et réseau',
    '11-themes-polices': 'Thèmes et polices', '12-ia-local': 'IA locale',
    '13-jeux': 'Jeux', '80-autres-a-choisir': 'Autres logiciels',
    '91-depots-a-revoir': 'Outils supplémentaires',
}


def safe_label(label):
    return label.replace('|', '/').replace(',', ' ·')


def retryable(args):
    return bool(args) and (args[0] in {'pacman', 'pacstrap'}
                           or (args[0] == 'arch-chroot' and len(args) > 2
                               and args[2] in {'mkinitcpio', 'systemctl', 'locale-gen'}))


class Ui:
    def __init__(self):
        self.gum = shutil.which('gum') if sys.stdin.isatty() and sys.stdout.isatty() else None
        self.log = None

    def call(self, *args):
        result = subprocess.run([self.gum, *args], text=True, stdout=subprocess.PIPE)
        if result.returncode:
            raise KeyboardInterrupt
        return result.stdout.rstrip('\n')

    def banner(self, subtitle='Installation depuis le live · sans chiffrement'):
        self.box('Arch · Hyprland · Quickshell\n' + subtitle)

    def box(self, text):
        if self.gum:
            subprocess.run([self.gum, 'style', '--border', 'rounded', '--border-foreground',
                            '117', '--padding', '1 2', '--', text], check=True)
        else:
            print('\n' + text + '\n')

    def header(self, number, title):
        self.box(f'{number}/6 · {title}')
        if self.log:
            with self.log.open('a') as stream:
                stream.write(f'\n### {number}/6 {title}\n')

    def input(self, prompt, default=''):
        if self.gum:
            return self.call('input', '--header', prompt, '--value', default, '--width', '70')
        return input(prompt + (f' [{default}]' if default else '') + ' : ').strip() or default

    def choose(self, prompt, choices, default=None):
        """choices = [(libellé, valeur)]. Les valeurs ne sont jamais du code shell."""
        if self.gum:
            args = ['choose', '--header', prompt, '--height', '15', '--label-delimiter', '|']
            if default is not None:
                args += ['--selected', next(safe_label(label) for label, value in choices if value == default)]
            return self.call(*args, '--', *(f'{safe_label(label)}|{value}' for label, value in choices))
        print(prompt)
        for n, (label, _) in enumerate(choices, 1):
            print(f'  {n}) {label}')
        while True:
            value = input('Numéro : ').strip()
            if value.isdigit() and 1 <= int(value) <= len(choices):
                return choices[int(value) - 1][1]

    def multi(self, prompt, choices, selected):
        if not choices:
            return set()
        if self.gum:
            args = ['choose', '--no-limit', '--header', prompt, '--height', '15',
                    '--label-delimiter', '|', '--selected', ','.join(safe_label(label) for label, value in choices if value in selected)]
            result = self.call(*args, '--', *(f'{safe_label(label)}|{value}' for label, value in choices))
            return set(result.splitlines()) if result else set()
        print(prompt)
        kept = set()
        for label, value in choices:
            default = 'oui' if value in selected else 'non'
            if self.input(label + ' (oui/non)', default) == 'oui':
                kept.add(value)
        return kept

    def selections(self, rows):
        packages = [r for r in rows if r['kind'] == 'paquet' and not r['locked']]
        groups = sorted({r['group'] for r in packages})
        defaults = {r['group'] for r in packages if r['default']}
        groups_kept = self.multi('Familles de logiciels · x : cocher · Entrée : valider',
                                 [(GROUPS.get(g, g), g) for g in groups], defaults)
        # Dans une famille retenue, garder ses valeurs par défaut ; une famille ajoutée
        # part de tous ses paquets et peut ensuite être affinée.
        chosen = {r['id'] for r in packages if r['group'] in groups_kept
                  and (r['default'] or r['group'] not in defaults)}
        if self.choose('Personnaliser les logiciels de chaque famille ?',
                       [('Conserver cette sélection', 'non'), ('Cocher/décocher les paquets', 'oui')]) == 'oui':
            for group in sorted(groups_kept):
                options = [r for r in packages if r['group'] == group]
                kept = self.multi(GROUPS.get(group, group), [(r['name'], r['id']) for r in options], chosen & {r['id'] for r in options})
                chosen -= {r['id'] for r in options}
                chosen |= kept
        configs = [r for r in rows if r['kind'] == 'configuration' and not r['locked']]
        chosen |= self.multi('Ta configuration personnelle', [(r['name'], r['id']) for r in configs],
                             {r['id'] for r in configs if r['default']})
        return [r for r in rows if r['id'] in chosen]

    def command(self, args, capture=False, interactive=False):
        """Conserve la sortie des commandes dans le live ; jamais les entrées passwd."""
        if self.log is None or interactive:
            result = subprocess.run(args, check=True, text=True,
                                    stdout=subprocess.PIPE if capture else None)
            return result.stdout.strip() if capture else ''
        title = ' '.join(str(a) for a in args)
        display = 'Installation des paquets avec pacstrap' if args[0] == 'pacstrap' else title
        with self.log.open('a') as log:
            log.write('\n+ ' + title + '\n')
            log.flush()
            if capture:
                result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=log)
                log.write(result.stdout)
                result.check_returncode()
                return result.stdout.strip()
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            spinner = None
            try:
                if self.gum:
                    spinner = subprocess.Popen([self.gum, 'spin', '--title', display, '--', 'bash', '-c',
                        'while kill -0 "$1" 2>/dev/null; do sleep 0.2; done', 'wait', str(process.pid)])
                else:
                    print('…', display, flush=True)
                code = process.wait()
            except BaseException:
                process.terminate()
                process.wait()
                raise
            finally:
                if spinner:
                    spinner.wait(timeout=5)
            if code:
                print('\n'.join(self.log.read_text().splitlines()[-20:]), file=sys.stderr)
                # Rejouer un téléchargement/configuration ; jamais relancer un formatage.
                if self.gum and retryable(args):
                    while True:
                        action = self.choose('Cette commande a échoué · journal : ' + str(self.log),
                            [('Arrêter', 'abort'), ('Réessayer cette commande', 'retry'),
                             ('Ouvrir un shell de diagnostic puis revenir', 'shell')])
                        if action == 'shell':
                            subprocess.run(['bash', '--noprofile', '--norc'])
                            continue
                        if action == 'retry':
                            return self.command(args, capture=capture, interactive=interactive)
                        raise RuntimeError('Arrêt demandé après échec de la commande. Consulter le journal.')
                raise subprocess.CalledProcessError(code, args)
            print('✓', display)
            return ''


UI = Ui()
