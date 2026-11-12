-- ============================================================
-- HYPRLAND LUA - RACCOURCIS CLAVIER (Noctalia v5+)
-- ============================================================

local home = os.getenv("HOME") or ""
local scripts = home .. "/.config/hypr/Scripts"
local mod = "SUPER"
local noctalia = "noctalia msg "

local terminal = "kitty"
local editor = "code"
local explorer = "thunar"
local browser = scripts .. "/browser-launcher.sh"
local move_step = 30

-- Les descriptions sont visibles via : hyprctl binds
local function bind(keys, dispatcher, description, flags)
	flags = flags or {}
	flags.description = description
	hl.bind(keys, dispatcher, flags)
end

local directions = {
	left = { x = -move_step, y = 0 },
	right = { x = move_step, y = 0 },
	up = { x = 0, y = -move_step },
	down = { x = 0, y = move_step },
}

local function resize_window(direction)
	return function()
		local delta = directions[direction]
		hl.dispatch(hl.dsp.window.resize({
			x = delta.x,
			y = delta.y,
			relative = true,
		}))
	end
end

local function move_or_swap(direction)
	return function()
		local window = hl.get_active_window()
		if window and window.floating then
			local delta = directions[direction]
			hl.dispatch(hl.dsp.window.move({
				x = delta.x,
				y = delta.y,
				relative = true,
			}))
		else
			hl.dispatch(hl.dsp.window.move({ direction = direction }))
		end
	end
end

-- 1. APPLICATIONS
bind(mod .. " + RETURN", hl.dsp.exec_cmd(terminal), "Ouvrir Kitty")
bind(mod .. " + E", hl.dsp.exec_cmd(explorer), "Ouvrir Thunar")
bind(mod .. " + C", hl.dsp.exec_cmd(editor), "Ouvrir VS Code")
bind(mod .. " + B", hl.dsp.exec_cmd(browser), "Ouvrir le navigateur")
bind(mod .. " + S", hl.dsp.exec_cmd("steam"), "Ouvrir Steam")

-- 2. NOCTALIA V5 : commandes IPC officielles
bind(mod .. " + D", hl.dsp.exec_cmd(noctalia .. "panel-toggle launcher"), "Noctalia : lanceur")
bind(mod .. " + L", hl.dsp.exec_cmd(noctalia .. "session lock"), "Noctalia : verrouiller")
bind(mod .. " + T", hl.dsp.exec_cmd(noctalia .. "settings-toggle"), "Noctalia : paramètres")
bind(mod .. " + N", hl.dsp.exec_cmd(noctalia .. "panel-toggle control-center"), "Noctalia : centre de contrôle")

-- Ces anciens raccourcis concernaient des plugins de Noctalia Shell v4.
-- Ils ne doivent PAS être recopiés sans identifier les plugins v5 installés.
-- SUPER + H : ancien plugin keybind-cheatsheet
-- SUPER + K : ancien plugin hyprland-keybinds
-- Pour un plugin v5 avec entrée [[panel]] :
-- bind(mod .. " + H", hl.dsp.exec_cmd(noctalia ..
--     "panel-toggle auteur/plugin:panel"), "Noctalia : aide raccourcis")

-- 3. FENÊTRES
bind(mod .. " + Q", hl.dsp.window.close(), "Fermer la fenêtre")
bind(mod .. " + W", hl.dsp.window.float({ action = "toggle" }), "Basculer fenêtre flottante")
bind(mod .. " + F", hl.dsp.window.fullscreen(), "Plein écran")

-- Sélecteur visuel Noctalia (remplace le cycle brut Hyprland)
bind("ALT + tab", hl.dsp.exec_cmd(noctalia .. "window-switcher hold"), "Noctalia : changer de fenêtre")

for _, direction in ipairs({ "left", "right", "up", "down" }) do
	bind(mod .. " + " .. direction, hl.dsp.focus({ direction = direction }), "Focus fenêtre : " .. direction)
	bind(mod .. " + SHIFT + " .. direction, resize_window(direction), "Redimensionner : " .. direction)
	bind(mod .. " + SHIFT + CTRL + " .. direction, move_or_swap(direction), "Déplacer/échanger : " .. direction)
end

-- 4. ESPACES DE TRAVAIL
bind(mod .. " + tab", hl.dsp.exec_cmd(scripts .. "/workspace.sh"), "Bureau suivant (script personnalisé)")
bind(mod .. " + SHIFT + tab", hl.dsp.focus({ workspace = "m-1" }), "Bureau précédent (moniteur)")

for i = 1, 10 do
	local key = tostring(i % 10) -- Le bureau 10 utilise la touche 0
	bind(mod .. " + " .. key, hl.dsp.focus({ workspace = i }), "Aller au bureau " .. i)
	bind(mod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }), "Envoyer la fenêtre au bureau " .. i)
end

bind(mod .. " + CTRL + right", hl.dsp.focus({ workspace = "r+1" }), "Bureau relatif suivant")
bind(mod .. " + CTRL + left", hl.dsp.focus({ workspace = "r-1" }), "Bureau relatif précédent")
bind(mod .. " + CTRL + down", hl.dsp.focus({ workspace = "empty" }), "Premier bureau vide")
bind(mod .. " + CTRL + ALT + right", hl.dsp.window.move({ workspace = "r+1" }), "Déplacer vers bureau suivant")
bind(mod .. " + CTRL + ALT + left", hl.dsp.window.move({ workspace = "r-1" }), "Déplacer vers bureau précédent")
bind(mod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), "Bureau suivant à la molette")
bind(mod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }), "Bureau précédent à la molette")

-- 5. SOURIS
bind(mod .. " + mouse:272", hl.dsp.window.drag(), "Déplacer à la souris", { mouse = true })
bind(mod .. " + mouse:273", hl.dsp.window.resize(), "Redimensionner à la souris", { mouse = true })
bind(mod .. " + X", hl.dsp.window.resize(), "Redimensionnement interactif")

-- 6. CAPTURES D'ÉCRAN
-- Le dossier est créé à la demande par le shell si nécessaire.
local shots = home .. "/Pictures/Screenshots"
local shotprefix = "mkdir -p '" .. shots .. "' && HYPRSHOT_DIR='" .. shots .. "' hyprshot -m "
bind(mod .. " + PRINT", hl.dsp.exec_cmd(shotprefix .. "window"), "Capture : fenêtre")
bind("ALT + PRINT", hl.dsp.exec_cmd(shotprefix .. "output"), "Capture : écran")
bind("SHIFT + PRINT", hl.dsp.exec_cmd(shotprefix .. "region"), "Capture : région")
bind(
	mod .. " + A",
	hl.dsp.exec_cmd(
		'mkdir -p "'
			.. shots
			.. '" && grim -g "$(slurp)" - | satty --filename - --output-filename "'
			.. shots
			.. '/Screenshot-$(date +%Y%m%d-%H%M%S).png"'
	),
	"Capture : annoter avec Satty"
)

-- 7. MULTIMÉDIA (PipeWire + playerctl)
bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), "Lecture / pause", { locked = true })
bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), "Morceau suivant", { locked = true })
bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), "Morceau précédent", { locked = true })
bind(
	"XF86AudioRaiseVolume",
	hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"),
	"Augmenter le volume",
	{ repeating = true, locked = true }
)
bind(
	"XF86AudioLowerVolume",
	hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%-"),
	"Baisser le volume",
	{ repeating = true, locked = true }
)
bind(
	"XF86AudioMute",
	hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),
	"Couper / rétablir le son",
	{ locked = true }
)
bind(
	"XF86MonBrightnessUp",
	hl.dsp.exec_cmd("brightnessctl set 5%+"),
	"Augmenter la luminosité",
	{ repeating = true, locked = true }
)
bind(
	"XF86MonBrightnessDown",
	hl.dsp.exec_cmd("brightnessctl set 5%-"),
	"Baisser la luminosité",
	{ repeating = true, locked = true }
)

-- Activer le passthrough avec SUPER + SHIFT + P
hl.bind("SUPER + SHIFT + P", hl.dsp.submap("passthru"))

-- Dans ce mode, les raccourcis Hyprland sont désactivés
hl.define_submap("passthru", function()
	-- Revenir aux raccourcis normaux
	hl.bind("SUPER + Escape", hl.dsp.submap("reset"))
end)
