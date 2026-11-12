#!/usr/bin/env bash

SESSIONS=$(tmux list-sessions -F "#S" 2>/dev/null)

menu() {
    printf "➕ Nouvelle session\n"
    printf "📁 Sessions existantes\n"
    printf "🔌 Connexion SSH\n"
    printf "❌ Quitter\n"
}

choice=$(menu | fzf \
    --prompt="tmux > " \
    --height=100% \
    --border=rounded)

case "$choice" in
    "➕ Nouvelle session")
        read -p "Nom de la session : " name
        [ -n "$name" ] && tmux new-session -ds "$name" && tmux switch-client -t "$name"
        ;;
    "📁 Sessions existantes")
        echo "$SESSIONS" | fzf --prompt="session > " | xargs tmux switch-client -t
        ;;
    "🔌 Connexion SSH")
        ~/.config/tmux/scripts/tmux-ssh.sh
        ;;
esac

