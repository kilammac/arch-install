#!/usr/bin/env bash
# Lanceur autonome : télécharge le dossier complet si seul ce fichier est présent.
set -Eeuo pipefail
SELF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE=install
BRANCH=main
ensure_network() {
  local reply
  until curl -fsS --max-time 15 -o /dev/null https://archlinux.org; do
    [[ -t 0 ]] || { echo 'Connexion Internet requise.' >&2; exit 1; }
    read -r -p 'Internet indisponible. Ouvrir iwctl pour le Wi-Fi ? [o/N] ' reply
    case "$reply" in
      o|O|oui) iwctl ;;
      *) exit 1 ;;
    esac
  done
}
while (($#)); do
  case "$1" in
    --help|-h)
      cat <<'HELP'
Arch · Hyprland · Quickshell — installation depuis le live officiel
Usage : bash install.sh [--check | --preview | --dry-run] [--branch NOM]
  --check       vérifier les fichiers locaux sans installation
  --preview     essayer les menus sans installation ni modification de disque
  --dry-run     alias de --preview
  --branch NOM  branche téléchargée si le lanceur est utilisé seul (main par défaut)
HELP
      exit 0 ;;
    --check) MODE=check ;;
    --preview|--dry-run) MODE=preview ;;
    --branch)
      [[ $# -ge 2 && $2 =~ ^[A-Za-z0-9._/-]+$ ]] || { echo 'Branche invalide.' >&2; exit 2; }
      BRANCH=$2
      shift ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
  shift
done
if [[ $MODE == install ]]; then
  [[ $EUID == 0 && -d /run/archiso ]] || {
    echo 'Installation autorisée uniquement comme root depuis le live ISO Arch.' >&2
    exit 1
  }
  [[ $(uname -m) == x86_64 ]] || { echo 'Architecture x86_64 requise.' >&2; exit 1; }
fi
PROJECT=""
for candidate in "$SELF_DIR" "$SELF_DIR/.."; do
  if [[ -f $candidate/installer.py && -f $candidate/payload/manifest.json && -f $candidate/catalogue/choix.json ]]; then
    PROJECT=$(cd -- "$candidate" && pwd)
    break
  fi
done
if [[ -z $PROJECT ]]; then
  [[ $MODE == install ]] || { echo 'Pour vérifier/prévisualiser, cloner le dépôt complet.' >&2; exit 1; }
  ensure_network
  PROJECT=$(mktemp -d /tmp/arch-personnel.XXXXXXXX)
  echo "Téléchargement de l’installateur complet dans $PROJECT…"
  curl -fL --retry 3 --connect-timeout 20 "https://codeload.github.com/kilammac/arch-install/tar.gz/refs/heads/$BRANCH" -o "$PROJECT/source.tar.gz"
  tar -xzf "$PROJECT/source.tar.gz" --strip-components=1 -C "$PROJECT"
  exec bash "$PROJECT/install.sh"
fi
cd -- "$PROJECT"
if [[ $MODE == check || $MODE == preview ]]; then
  command -v python >/dev/null || { echo 'Python 3 est requis pour ce contrôle local.' >&2; exit 1; }
  exec python -B installer.py "--$MODE"
fi
# Installation dans le live uniquement ; les garde-fous précédents sont déjà appliqués.
needed=()
command -v python >/dev/null || needed+=(python)
command -v gum >/dev/null || needed+=(gum)
if ((${#needed[@]})); then
  ensure_network
  echo 'Préparation de l’interface dans le live (connexion Internet requise)…'
  pacman -Sy --needed --noconfirm "${needed[@]}"
fi
exec python -B installer.py
