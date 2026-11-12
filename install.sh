#!/usr/bin/env bash
# Point d'entrée du live ISO. Aucun code de formatage n'est exécuté par --check.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "${1:-}" in
  --help|-h)
    cat <<'EOF'
Usage : bash install.sh [--check]
  sans option : questionnaire et installation depuis le live ISO Arch x86_64
  --check     : vérification locale, sans installation ni formatage
Copier tout ce dossier sur une clé. Voir DEMARRER-ICI.md.
EOF
    exit 0 ;;
  --check)
    command -v python >/dev/null || { echo 'Python 3 requis pour la vérification.'; exit 1; }
    exec python -B installer.py --check ;;
  '') ;;
  *) echo 'Option inconnue. Utiliser --help.' >&2; exit 2 ;;
esac
[[ $EUID == 0 && -d /run/archiso ]] || {
  echo 'Installation autorisée uniquement comme root depuis le live ISO Arch.' >&2
  exit 1
}
[[ $(uname -m) == x86_64 ]] || { echo 'Architecture x86_64 requise.'; exit 1; }
if ! command -v python >/dev/null; then
  echo 'Installation de Python dans le live uniquement (connexion Internet requise).'
  pacman -Sy --needed --noconfirm python
fi
exec python -B installer.py
