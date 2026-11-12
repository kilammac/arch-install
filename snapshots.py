"""Snapshots Snapper sur le sous-volume racine ; aucune restauration implicite."""
import re

MODES = {'none', 'manual', 'auto'}


def packages(mode):
    if mode not in MODES:
        raise ValueError('Mode de snapshots inconnu.')
    return {'snapper', 'snap-pac'} if mode == 'auto' else ({'snapper'} if mode == 'manual' else set())


def configure(target, mode, chroot):
    if mode == 'none':
        return
    packages(mode)
    # Écrire le profil directement : create-config échoue si @snapshots existe déjà.
    template = target / 'etc/snapper/config-templates/default'
    if not template.is_file():
        template = target / 'usr/share/snapper/config-templates/default'
    text = template.read_text()
    values = {'SUBVOLUME': '/', 'FSTYPE': 'btrfs', 'NUMBER_CLEANUP': 'yes',
              'NUMBER_LIMIT': '10', 'NUMBER_LIMIT_IMPORTANT': '5',
              'TIMELINE_CREATE': 'yes' if mode == 'auto' else 'no',
              'TIMELINE_CLEANUP': 'yes', 'TIMELINE_LIMIT_HOURLY': '3',
              'TIMELINE_LIMIT_DAILY': '7', 'TIMELINE_LIMIT_WEEKLY': '0',
              'TIMELINE_LIMIT_MONTHLY': '0', 'TIMELINE_LIMIT_YEARLY': '0'}
    for key, value in values.items():
        if re.search(r'^' + key + '=', text, re.M):
            text = re.sub(r'^' + key + '=.*$', f'{key}="{value}"', text, flags=re.M)
        else:
            text += f'\n{key}="{value}"\n'
    path = target / 'etc/snapper/configs/root'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o640)
    path = target / 'etc/conf.d/snapper'
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ''
    match = re.search(r'^SNAPPER_CONFIGS="([^"]*)"', text, re.M)
    names = match.group(1).split() if match else []
    if 'root' not in names:
        names.append('root')
    setting = 'SNAPPER_CONFIGS="' + ' '.join(names) + '"'
    text = re.sub(r'^SNAPPER_CONFIGS=.*$', setting, text, flags=re.M) if match else text + '\n' + setting + '\n'
    path.write_text(text)
    chroot('snapper', '--no-dbus', '-c', 'root', 'get-config')
    chroot('systemctl', 'enable', 'snapper-cleanup.timer')
    if mode == 'auto':
        chroot('systemctl', 'enable', 'snapper-timeline.timer')


def initial(chroot):
    # La description sert à reconnaître une création réussie avant une coupure.
    description = 'arch-personnel-installation-initiale'
    existing = chroot('snapper', '--no-dbus', '--csvout', '-c', 'root', 'list',
                      '--columns', 'number,description', capture=True)
    if description not in existing:
        chroot('snapper', '--no-dbus', '-c', 'root', 'create', '--description', description,
               '--cleanup-algorithm', 'number')
