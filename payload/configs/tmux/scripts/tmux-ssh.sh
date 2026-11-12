#!/usr/bin/env bash

HOSTS="$HOME/.config/tmux/ssh_hosts"

[ ! -f "$HOSTS" ] && exit 0

host=$(cat "$HOSTS" | fzf --prompt="ssh > ")

[ -z "$host" ] && exit 0

session="ssh-$(echo "$host" | tr '.@' '_')"

tmux new-session -ds "$session" "ssh $host"
tmux switch-client -t "$session"

