"""Journal JSON atomique, sans mot de passe ni exécution de fichiers de réponses."""
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

RELATIVE = Path('var/lib/arch-personnel-install/state.json')
STEPS = {'filesystem', 'base', 'locale', 'account', 'password-set', 'root-password-set', 'boot',
         'services', 'deploy', 'snapshots', 'options', 'initial-snapshot', 'verify'}


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('État de reprise inconnu.')
    if not isinstance(data.get('settings'), dict) or not isinstance(data.get('completed'), list):
        raise ValueError('État de reprise incomplet.')
    if not isinstance(data.get('revision'), int) or data['revision'] < 0 or not isinstance(data.get('finished'), bool):
        raise ValueError('Révision ou statut de reprise invalide.')
    if not isinstance(data.get('session_id'), str) or not re.fullmatch(r'[0-9a-f]{32}', data['session_id']):
        raise ValueError('Identifiant de session invalide.')
    if set(data['completed']) - STEPS or len(data['completed']) != len(set(data['completed'])):
        raise ValueError('Étapes de reprise invalides.')
    if data.get('in_progress') not in STEPS | {None}:
        raise ValueError('Étape en cours invalide.')
    if data.get('layout') is not None and (not isinstance(data['layout'], dict)
                                          or data.get('mode') not in {'effacer', 'partitions'}):
        raise ValueError('Disposition ou mode disque enregistré invalide.')
    def no_secrets(item):
        if isinstance(item, dict):
            if any(str(key).lower() in {'password', 'passwd', 'token', 'secret',
                                       'credentials', 'user_password', 'root_password'} for key in item):
                raise ValueError('Un état ne doit pas contenir de secret.')
            for value in item.values():
                no_secrets(value)
        elif isinstance(item, list):
            for value in item:
                no_secrets(value)
    no_secrets(data)
    return data


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Session:
    def __init__(self, data, paths, log=None):
        self.data = validate(data)
        self.paths = [Path(p) for p in dict.fromkeys(paths)]
        self.log = log

    @classmethod
    def create(cls, settings, path, log=None):
        session = cls({'schema': 1, 'revision': 0, 'settings': settings,
                       'session_id': uuid.uuid4().hex,
                       'completed': [], 'in_progress': None, 'layout': None,
                       'finished': False}, [path], log)
        session.save()
        return session

    @classmethod
    def load(cls, path, log=None):
        path = Path(path)
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError('Fichier d’état refusé.')
        return cls(json.loads(path.read_text()), [path], log)

    def attach(self, path):
        path = Path(path)
        if path not in self.paths:
            self.paths.insert(0, path)
        self.save()

    def save(self):
        validate(self.data)
        self.data['revision'] += 1
        for path in self.paths:
            atomic_json(path, self.data)
            if self.log and Path(self.log).is_file():
                destination = path.parent / 'install.log'
                if destination.resolve() != Path(self.log).resolve():
                    shutil.copyfile(self.log, destination)
                    destination.chmod(0o600)

    def done(self, name):
        return name in self.data['completed']

    def perform(self, name, action):
        if self.done(name):
            return
        self.data['in_progress'] = name
        self.data.pop('last_error', None)
        self.save()
        try:
            result = action()
        except BaseException as error:
            self.data['last_error'] = {'stage': name, 'type': type(error).__name__}
            self.save()
            raise
        self.data['completed'].append(name)
        self.data['in_progress'] = None
        self.save()
        return result
