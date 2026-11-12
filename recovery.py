"""Reconnaître et remonter une cible existante ; ce module ne formate rien."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

from session_state import Session, RELATIVE

SUBVOLS = {'@': '', '@home': 'home', '@log': 'var/log', '@pkg': 'var/cache/pacman/pkg',
           '@snapshots': '.snapshots', '@installstate': 'var/lib/arch-personnel-install'}


def disk_identity(disk):
    return {key: disk.get(key) for key in ['size', 'model', 'serial']}


def uuid_of(device, run):
    return run('blkid', '-s', 'UUID', '-o', 'value', device, capture=True)


def resolve_layout(layout, nodes, target, run):
    if not isinstance(layout, dict) or not re.fullmatch(r'[0-9a-fA-F-]{36}', str(layout.get('root_uuid', ''))):
        raise ValueError('UUID racine absent ou invalide : aucune reprise du formatage.')
    def resolve(uuid):
        if not isinstance(uuid, str) or not re.fullmatch(r'[0-9a-fA-F-]{4,36}', uuid):
            raise ValueError('UUID de partition invalide.')
        device = run('blkid', '-U', uuid, capture=True)
        if not re.fullmatch(r'/dev/[a-zA-Z0-9/_-]+', device):
            raise RuntimeError('La partition enregistrée est introuvable.')
        return device
    root = resolve(layout['root_uuid'])
    esp = resolve(layout['esp_uuid']) if layout.get('esp_uuid') else None
    def walk(node):
        yield node
        for child in node.get('children', []):
            yield from walk(child)
    disks = [n for n in nodes if n.get('type') == 'disk' and any(c.get('name') == root for c in walk(n))]
    if len(disks) != 1 or disk_identity(disks[0]) != layout.get('disk_identity'):
        raise RuntimeError('L’identité du disque de reprise ne correspond pas. Aucun formatage autorisé.')
    disk = disks[0]
    if esp and not any(c.get('name') == esp for c in walk(disk)):
        raise RuntimeError('La partition EFI enregistrée n’appartient pas au disque de reprise.')
    for node in walk(disk):
        if node.get('ro'):
            raise RuntimeError('Disque de reprise en lecture seule.')
        for mount in node.get('mountpoints') or []:
            if mount and not Path(mount).is_relative_to(target):
                raise RuntimeError('Une partition du disque est utilisée ailleurs : ' + mount)
    return disk, root, esp


def mounted(path):
    result = subprocess.run(['findmnt', '--json', '--mountpoint', str(path), '-o', 'UUID,FSROOT'],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode:
        return None
    filesystems = json.loads(result.stdout).get('filesystems', [])
    return filesystems[0] if filesystems else None


def mount_existing(target, root, esp, layout, run):
    def ensure(path, device, uuid, subvol=None):
        current = mounted(path)
        if current:
            expected = '/' + subvol if subvol else '/'
            if str(current.get('uuid', '')).lower() != uuid.lower() or current.get('fsroot') != expected:
                raise RuntimeError('Montage différent de la cible enregistrée : ' + str(path))
            return
        path.mkdir(parents=True, exist_ok=True)
        options = f'subvol={subvol},compress=zstd:3,noatime' if subvol else 'umask=0077'
        run('mount', '-o', options, device, path)
    ensure(target, root, layout['root_uuid'], '@')
    for subvol, relative in SUBVOLS.items():
        if relative:
            ensure(target / relative, root, layout['root_uuid'], subvol)
    if esp:
        ensure(target / 'boot', esp, layout['esp_uuid'])


def discover(runtime, target, explicit=None):
    """Chercher l’état du live puis des seules partitions portant notre label."""
    candidates = []
    for path in [explicit, runtime, target / RELATIVE]:
        if path and Path(path).is_file():
            session = Session.load(path)
            candidates.append((str(path), session.data))
    result = subprocess.run(['blkid', '-t', 'LABEL=ArchRoot', '-o', 'device'],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for device in result.stdout.splitlines():
        if not re.fullmatch(r'/dev/[a-zA-Z0-9/_-]+', device):
            continue
        with tempfile.TemporaryDirectory(prefix='arch-recovery-', dir='/run') as directory:
            mount = subprocess.run(['mount', '-o', 'ro,subvol=@installstate,nosuid,nodev,noexec', device, directory],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if mount.returncode:
                continue
            try:
                path = Path(directory) / 'state.json'
                if path.is_file():
                    candidates.append((device, Session.load(path).data))
            finally:
                subprocess.run(['umount', directory], check=True)
    # Plusieurs copies d'une session : retenir la révision la plus récente.
    latest = {}
    for origin, data in candidates:
        key = data.get('session_id') or json.dumps(data['settings'], sort_keys=True)
        if key not in latest or data['revision'] > latest[key][1]['revision']:
            latest[key] = (origin, data)
    return list(latest.values())
