"""Déploiement des configurations embarquées, uniquement dans une cible neuve."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ensure_link(link, destination):
    if link.is_symlink() and str(link.readlink()) == destination:
        return
    if link.exists() or link.is_symlink():
        raise RuntimeError(f'Un autre fichier occupe le lien attendu : {link}')
    link.symlink_to(destination)


def config_packages(selected):
    ids = {r['id'] for r in selected}
    result = set()
    requirements = {
        'cfg:hypr': 'hyprland kitty xorg-xwayland xdg-desktop-portal-hyprland xdg-desktop-portal-gtk gnome-keyring',
        'cfg:quickshell': 'quickshell qt6-multimedia qt6-websockets qt6-svg qt6-5compat qt6-imageformats pipewire pipewire-pulse wireplumber brightnessctl ddcutil cliphist wl-clipboard slurp grim satty playerctl cava mpv yt-dlp deno jq curl matugen network-manager-applet gnome-keyring upower polkit fprintd libnotify btop htop nvtop dmidecode',
        'cfg:nvim': 'neovim git', 'cfg:kitty': 'kitty', 'cfg:fish': 'fish fastfetch starship',
        'cfg:starship': 'starship', 'cfg:tmux': 'tmux', 'cfg:foot': 'foot',
        'cfg:gtk': 'adw-gtk-theme papirus-icon-theme',
        'cfg:qt': 'qt5ct qt6ct kvantum qt5-wayland qt6-wayland',
    }
    for key, packages in requirements.items():
        if key in ids:
            result.update(packages.split())
    if 'cfg:hypr' in ids:
        result.update('firefox yazi ttf-jetbrains-mono-nerd noto-fonts noto-fonts-emoji'.split())
    if 'cfg:quickshell' in ids:
        result.add('papirus-icon-theme')
    return result


def deploy(target, user, selected, keymap, installed, login_shell='bash'):
    home = target / 'home' / user
    entries = json.loads((ROOT / 'payload/entries.json').read_text())
    ids = {r['id'] for r in selected}
    for key in ids:
        for entry in entries.get(key, []):
            source = ROOT / 'payload' / entry['source']
            destination = home / entry['destination']
            if not destination.is_relative_to(home) or '..' in Path(entry['destination']).parts:
                raise ValueError('Destination de configuration invalide')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)

    def put(relative, text, mode=0o644):
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    for part in ['hypr', 'quickshell', 'nvim']:
        if 'cfg:' + part in ids:
            link = home / '.config' / part
            link.parent.mkdir(parents=True, exist_ok=True)
            ensure_link(link, '../.my-hyprland/' + part)

    if 'cfg:hypr' in ids:
        hypr = '.my-hyprland/hypr/'
        put(hypr + 'monitors.lua', '-- Détection automatique des écrans de cette machine.\nhl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })\n')
        put(hypr + 'workspaces.lua', '-- Aucun écran imposé : espaces gérés par Hyprland.\nreturn {}\n')
        for name in ['config/input.lua', 'modules/inputs.lua']:
            path = home / hypr / name
            path.write_text(path.read_text().replace('kb_layout = "us"', f'kb_layout = "{keymap}"').replace('kb_layout  = "us"', f'kb_layout  = "{keymap}"'))
        keymaps = home / hypr / 'config/keymaps.lua'
        text = keymaps.read_text().replace('local browser = "zen-browser"', 'local browser = "firefox"')
        text = text.replace('local browser_alt = "brave"', 'local browser_alt = "firefox"')
        text = text.replace('launchApp("files")', 'launchApp(inTerminal("yazi"))')
        lines = []
        for line in text.splitlines():
            if ('.config/custom_scripts/' in line or '~/dotfiles/' in line
                    or ('quickshell:' in line and 'cfg:quickshell' not in ids)):
                line = '-- Non transporté : ' + line
            lines.append(line)
        keymaps.write_text('\n'.join(lines) + '\n')
        commands = ['dbus-update-activation-environment --systemd WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP XDG_SESSION_TYPE QT_QPA_PLATFORMTHEME',
                    'gnome-keyring-daemon --start --components=secrets']
        if 'cfg:quickshell' in ids:
            commands.append('systemctl --user restart quickshell.service')
        elif 'hyprpolkitagent' in installed:
            commands.append('/usr/lib/hyprpolkitagent/hyprpolkitagent')
        if 'easyeffects' in installed:
            commands.append('easyeffects --gapplication-service')
        startup = 'hl.env("XDG_CURRENT_DESKTOP", "Hyprland")\nhl.env("XDG_SESSION_TYPE", "wayland")\nhl.env("QT_QPA_PLATFORMTHEME", "qt6ct")\nhl.on("hyprland.start", function()\n'
        startup += '\n'.join('    hl.exec_cmd(' + json.dumps(command) + ')' for command in commands)
        startup += '\nend)\n'
        put(hypr + 'modules/startup.lua', startup)
    if 'cfg:quickshell' in ids:
        shell = home / '.my-hyprland/quickshell/shell.qml'
        shell.write_text(shell.read_text().replace('IconTheme kora-robot', 'IconTheme Papirus-Dark'))
        put('.config/systemd/user/quickshell.service', f'''[Unit]
Description=Bureau Quickshell personnel
After=graphical-session.target
PartOf=graphical-session.target
[Service]
Type=exec
ExecStart=/usr/bin/qs -p /home/{user}/.config/quickshell/shell.qml
Restart=on-failure
RestartSec=2
''')
        commands = home / '.my-hyprland/quickshell/core/constants/Commands.qml'
        commands.write_text(commands.read_text().replace('"zen-browser"', '"firefox"'))
        # Deux copies du helper dans les sources ; les panneaux utilisent scripts/gpu.
        for path in (home / '.my-hyprland/quickshell').glob('*/gpu/gpu.sh'):
            text = path.read_text()
            text = text.replace('nvidia | nouveau | "") echo 1 ;;',
                                'amdgpu) [ "$(cat "$SYS/bus/pci/devices/$2/boot_vga" 2>/dev/null)" = 1 ] && echo 0 || echo 1 ;;\n        nvidia | nouveau | "") echo 1 ;;')
            path.write_text(text)
            path.chmod(0o755)
        # Fonctions d'information matérielle en lecture seule ; aucun remplacement PAM global.
        system = home / '.my-hyprland/quickshell/system'
        for name, dest, mode in [('qs-hwinfo', 'usr/local/bin/qs-hwinfo', 0o755),
                                  ('qs-hwinfo.service', 'etc/systemd/system/qs-hwinfo.service', 0o644),
                                  ('qs-notif-origin', 'usr/local/bin/qs-notif-origin', 0o755)]:
            source = system / name
            output = target / dest
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
            output.chmod(mode)
            if name == 'qs-hwinfo':
                output.write_text(output.read_text().replace('RAPL=/sys/class/powercap/intel-rapl:0',
                    'RAPL=""\nfor zone in /sys/class/powercap/*-rapl:0; do\n    [ -r "$zone/energy_uj" ] && { RAPL=$zone; break; }\ndone'))
        wants = target / 'etc/systemd/system/multi-user.target.wants'
        wants.mkdir(parents=True, exist_ok=True)
        ensure_link(wants / 'qs-hwinfo.service', '/etc/systemd/system/qs-hwinfo.service')
    if 'cfg:kitty' in ids:
        path = home / '.config/kitty/kitty.conf'
        path.write_text(path.read_text().replace('MesloLGS NF', 'JetBrainsMono Nerd Font'))
    start = target / 'usr/local/bin/start-desktop'
    start.parent.mkdir(parents=True, exist_ok=True)
    start.write_text('''#!/bin/bash
if [[ $EUID == 0 ]]; then echo "Se connecter avec le compte utilisateur."; exit 1; fi
export XDG_CURRENT_DESKTOP=Hyprland XDG_SESSION_TYPE=wayland
if command -v start-hyprland >/dev/null; then start-hyprland; else Hyprland; fi
result=$?
systemctl --user stop quickshell.service 2>/dev/null || true
exit "$result"
''')
    start.chmod(0o755)
    # Le bureau démarre après authentification sur tty1 ; en quittant, on retrouve le shell.
    if 'hyprland' in installed:
        put('.bash_profile', '[[ -f ~/.bashrc ]] && . ~/.bashrc\nif [[ -z ${WAYLAND_DISPLAY:-} && ${XDG_VTNR:-} == 1 ]]; then\n    start-desktop\nfi\n')
        if login_shell == 'fish':
            put('.config/fish/conf.d/10-start-desktop.fish', 'if status is-login; and not set -q WAYLAND_DISPLAY; and test "$XDG_VTNR" = 1\n    start-desktop\nend\n')
    for file in (home / '.my-hyprland').rglob('*'):
        if file.is_file() and file.read_bytes().startswith(b'#!'):
            file.chmod(0o755)
