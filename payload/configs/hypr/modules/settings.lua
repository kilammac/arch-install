-- ========================================
-- HYPRLAND - PARAMÈTRES GÉNÉRAUX
-- ========================================

-- Couleurs dynamiques Noctalia
local colors = require("modules.noctalia.noctalia-colors")

hl.config({
	-- Disposition des fenêtres
	general = {
		layout = "master",
		col = colors.general.col,

		snap = {
			enabled = true,
		},
	},

	-- Configuration du layout Master
	master = {
		new_status = "master",
	},

	-- Paramètres divers
	misc = {
		disable_hyprland_logo = true,
		disable_splash_rendering = true,
		force_default_wallpaper = 0,
		allow_session_lock_restore = true,
	},

	-- Applications XWayland
	xwayland = {
		force_zero_scaling = true,
	},

	-- Groupes de fenêtres
	group = colors.group,
})
