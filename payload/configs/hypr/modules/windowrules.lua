-- ============================================================================
-- HYPRLAND - RÈGLES DES FENÊTRES (API Lua)
-- Fichier : ~/.config/hypr/modules/windowrules.lua
-- ============================================================================
-- Les règles sont évaluées dans l'ordre : une règle ultérieure peut modifier
-- le résultat d'une règle précédente qui cible la même fenêtre.
--
-- Pour identifier la classe et le titre réels d'une application :
--   hyprctl clients
-- Pour voir les erreurs après rechargement :
--   hyprctl configerrors
--
-- ATTENTION : les noms de classes sont sensibles aux majuscules/minuscules.
-- Les deux antislashs (\\) permettent d'échapper un point dans une regex Lua.
-- ============================================================================

-- 1. FENÊTRES FLOTTANTES ----------------------------------------------------
-- Ces applications s'ouvrent hors du pavage automatique (layout Master).
-- On conserve les applications de ton fichier initial, sans ajouter
-- arbitrairement de nouvelles applications à la liste.
local floating_classes = {
	"org.pulseaudio.pavucontrol", -- Contrôle du volume PulseAudio/PipeWire
	"de.haeckerfelix.Shortwave", -- Radio Internet
	"com.github.iwalton3.jellyfin-media-player", -- Lecteur Jellyfin
	"Signal", -- Messagerie Signal
	"com.github.rafostar.Clapper", -- Lecteur vidéo Clapper
	"app.drey.Warp", -- Transfert de fichiers
	"net.davidotek.pupgui2", -- ProtonUp-Qt
	"yad", -- Boîtes de dialogue YAD
	"eog", -- Visionneuse d'images
	"io.github.alainm23.planify", -- Gestionnaire de tâches
	"io.gitlab.theevilskeleton.Upscaler", -- Agrandissement d'images
	"com.github.unrud.VideoDownloader", -- Téléchargement de vidéos
	"io.gitlab.adhami3310.Impression", -- Application Impression
	"io.missioncenter.MissionCenter", -- Moniteur système
}

-- Les points dans les identifiants sont des points littéraux dans la regex.
-- Cela évite de les interpréter comme « n'importe quel caractère ».
for _, class in ipairs(floating_classes) do
	local pattern = "^" .. class:gsub("%.", "\\.") .. "$"
	hl.window_rule({
		match = { class = pattern },
		float = true,
	})
end

-- Dialogues du portail GTK : taille initiale proportionnelle à l'écran.
hl.window_rule({
	name = "gtk-portal-dialogs",
	match = { class = "^xdg-desktop-portal-gtk$" },
	float = true,
	size = { "monitor_w * 0.65", "monitor_h * 0.75" },
	center = true,
})

-- Les submaps contrôlent le passage des touches à la VM, plutôt que SPICE.
hl.window_rule({
	name = "spice-host-shortcuts",
	match = { class = "^(remote-viewer|virt-viewer)$" },
	no_shortcuts_inhibit = true,
})

-- 2. EMPÊCHER LA MISE EN VEILLE PENDANT UNE VIDÉO ---------------------------
-- En mode plein écran uniquement, les applications ci-dessous empêchent
-- normalement hypridle de lancer ses actions d'inactivité.
-- Une fenêtre non maximisée ne bloque donc pas la veille à cause de ces règles.
local fullscreen_media = {
	"^(.*celluloid.*|.*mpv.*|.*vlc.*)$", -- Lecteurs multimédias
	"^.*[Ss]potify.*$", -- Spotify
	"^(.*LibreWolf.*|.*floorp.*|.*brave-browser.*|.*firefox.*|.*chromium.*|.*zen.*|.*vivaldi.*)$",
	-- Navigateurs (vidéo en plein écran)
}

for _, pattern in ipairs(fullscreen_media) do
	hl.window_rule({
		match = { class = pattern },
		idle_inhibit = "fullscreen",
	})
end

-- 3. IMAGE DANS L'IMAGE (PICTURE-IN-PICTURE) -------------------------------
-- Une petite fenêtre vidéo reste visible au-dessus des autres fenêtres.
-- « pin » l'affiche sur tous les espaces de travail.
-- « size » et « move » sont ici exprimés en pourcentage de l'écran.
-- Le titre doit commencer par « Picture-in-Picture » (ou une variante).
-- Une seule règle suffit : inutile d'attribuer un tag intermédiaire.
hl.window_rule({
	match = { title = "^[Pp]icture.in.[Pp]icture.*$" },
	float = true,
	pin = true,
	keep_aspect_ratio = true,
	size = "25% 25%",
	move = "73% 72%",
})

-- 4. OPACITÉ ---------------------------------------------------------------
-- Les dizaines de règles « opacity = 1.0 » de l'ancien fichier ont été
-- retirées : elles n'ont généralement aucun effet lorsque l'opacité globale
-- de Hyprland est déjà à 1.0.
--
-- IMPORTANT : si modules/themes/theme.lua règle l'opacité globale à moins
-- de 1.0, il faut ajouter explicitement des exceptions pour les applications
-- devant rester opaques. Utiliser « override » pour forcer l'opacité absolue.
-- Exemple (désactivé volontairement) :
-- hl.window_rule({
--     match = { class = "^firefox$" },
--     opacity = "1.0 override 1.0 override 1.0 override",
-- })

-- 5. FENÊTRES TEMPORAIRES JETBRAINS ----------------------------------------
-- Empêche certaines fenêtres techniques intitulées « win123 » de voler
-- le focus au moment de leur apparition.
hl.window_rule({
	match = {
		class = "^.*jetbrains.*$",
		title = "^win[0-9]+$",
	},
	no_initial_focus = true,
})

-- Lecteur cassette Quickshell : fenêtre flottante dédiée.
hl.window_rule({
	match = { title = "^Cassette Deck$" },
	float = true,
})

-- Ignore self-maximize requests from apps (from the upstream example config)
hl.window_rule({
	name = "suppress-maximize-events",
	match = { class = ".*" },
	suppress_event = "maximize",
})
