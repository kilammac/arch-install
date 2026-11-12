#!/usr/bin/env python3
"""Recherche locale de motifs : affiche les emplacements, jamais les valeurs."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATTERNS = {
    'clé privée': r'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----',
    'jeton GitHub': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})',
    'clé OpenAI': r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}',
    'clé AWS': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'jeton Slack': r'\bxox[baprs]-[A-Za-z0-9-]{20,}',
    'clé Google': r'\bAIza[0-9A-Za-z_-]{30,}',
    'identifiants dans URL': r'\b[a-z][a-z0-9+.-]*://[^\s/<>"\']+:[^\s/<>"\']+@',
    'JWT': r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',
    'affectation de secret': r'''(?i)\b(?:[a-z_]*(?:token|api_?key|password|passwd|secret))\s*[:=]\s*["'][^"'\r\n]{8,}["']''',
}


def main():
    issues = []
    for file in sorted(ROOT.rglob('*')):
        relative = file.relative_to(ROOT)
        if '.git' in relative.parts or '__pycache__' in relative.parts:
            continue
        if file.is_symlink():
            issues.append((relative, 0, 'lien symbolique à examiner'))
            continue
        if not file.is_file():
            continue
        if file.name in {'auth.json', 'credentials', 'fish_variables', 'ssh_hosts', 'fast-token', '.env', 'id_rsa', 'id_ed25519'}:
            issues.append((relative, 0, 'fichier privé à exclure'))
        try:
            content = file.read_text()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if re.search(pattern, line):
                    # Une référence de variable n'est pas une valeur de secret embarquée.
                    if label == 'affectation de secret' and '${' in line:
                        continue
                    # Libellés d'interface Quickshell, examinés lors de l'audit initial.
                    if label == 'affectation de secret' and 'readonly property string failureNoSecrets:' in line:
                        continue
                    issues.append((relative, number, label))
    for path, line, label in issues:
        print(f'{path}:{line}: {label}')
    print(f'{len(issues)} correspondance(s). Scan de motifs uniquement : ce résultat ne garantit pas l’absence de tout secret.')
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
