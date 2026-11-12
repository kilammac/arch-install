-- ============================================================
-- HYPRLAND - ENVIRONNEMENT ET DÉMARRAGE AUTOMATIQUE
-- ============================================================
-- Ce module configure l'environnement des applications puis
-- lance les services de session au démarrage de Hyprland.
-- Il est chargé depuis le fichier principal hyprland.lua.

-- ------------------------------------------------------------
-- 1. VARIABLES D'ENVIRONNEMENT
-- ------------------------------------------------------------
-- Identifie le bureau pour les applications et portails XDG.
-- Si tu démarres Hyprland avec UWSM, ces variables peuvent déjà
-- être gérées par UWSM : évite alors les définitions en double.
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")

-- Utilise qt6ct pour les paramètres de thème des applications Qt.
-- Conserve cette ligne uniquement si qt6ct est bien installé.
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")

-- Mise à l'échelle automatique pour certaines applications Qt.
-- À tester avec l'écran 4K si une application présente un souci.
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

-- Désactive les décorations côté application dans certains logiciels Qt.
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")

-- Préférence Wayland pour certaines applications Electron.
-- Selon la version d'Electron, cette variable peut être ignorée.
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
--crash hyprland
hl.env("HYPRLAND_NO_RT", "1")

-- ------------------------------------------------------------
-- 2. APPLICATIONS LANCÉES UNE SEULE FOIS AU DÉMARRAGE
-- ------------------------------------------------------------
-- L'événement hyprland.start ne se déclenche pas lors d'un simple
-- rechargement de configuration : il évite donc les doublons.
local programmes_demarrage = {

	-- Agent d'autorisation Polkit : privilégie celui de Hyprland,
	-- puis tente l'agent GNOME si le premier est absent.
	-- "/usr/lib/hyprpolkitagent/hyprpolkitagent || /usr/libexec/polkit-gnome-authentication-agent-1",

	-- Trousseau de secrets GNOME (mots de passe des applications).
	"gnome-keyring-daemon --start --components=secrets",

	-- Effets et traitement audio PipeWire.
	"easyeffects",

	-- Interface Noctalia : barre, panneaux et widgets.
	-- "noctalia",
	-- "sh -c 'sleep 5; exec noctalia'",
	-- Décommenter si tu souhaites utiliser hypridle.
	-- "hypridle",
}

hl.on("hyprland.start", function()
	-- Rend les variables importantes accessibles à l'activation
	-- D-Bus et aux services utilisateur systemd.
	-- Démarre Quickshell seulement après la transmission de l'environnement.
	-- Le service systemd le relancera en cas de crash.
	hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP XDG_SESSION_TYPE QT_QPA_PLATFORMTHEME QT_AUTO_SCREEN_SCALE_FACTOR QT_WAYLAND_DISABLE_WINDOWDECORATION && systemctl --user restart quickshell.service")

	-- Lance les programmes définis ci-dessus.
	-- hl.exec_cmd est asynchrone : aucun « & » n'est nécessaire.
	for _, commande in ipairs(programmes_demarrage) do
		hl.exec_cmd(commande)
	end
end)
-- hl.on("hyprland.start", function()
-- 	hl.exec_cmd("sh -c 'sleep 5; exec noctalia'")
-- end)

-- Pas de « hyprctl reload » différé : Hyprland charge déjà
-- sa configuration au démarrage, et le rechargement artificiel
-- peut déclencher des effets secondaires inutiles.
