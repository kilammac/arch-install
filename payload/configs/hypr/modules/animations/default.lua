-- ============================================================================
-- HYPRLAND - ANIMATIONS PAR DÉFAUT
-- Fichier : ~/.config/hypr/modules/animations/default.lua
-- Chargé par : require("modules.animations.default")
-- ============================================================================

-- Active les animations dans Hyprland.
-- Pour les désactiver complètement, remplacer true par false.
hl.config({
    animations = {
        enabled = true,
    },
})

-- ============================================================================
-- 1. COURBES D'ANIMATION
-- ============================================================================
-- Une courbe de Bézier détermine l'accélération et le ralentissement du mouvement.
-- Les deux paires de coordonnées correspondent aux points de contrôle.
-- Une valeur Y supérieure à 1 (ou inférieure à 0) crée un léger dépassement.

-- Mouvement souple, avec un petit dépassement en fin de course.
hl.curve("wind", {
    type = "bezier",
    points = { { 0.05, 0.9 }, { 0.1, 1.05 } },
})

-- Apparition dynamique des fenêtres (effet de dépassement assumé).
hl.curve("winIn", {
    type = "bezier",
    points = { { 0.1, 1.1 }, { 0.1, 1.1 } },
})

-- Disparition des fenêtres avec une accélération non linéaire.
hl.curve("winOut", {
    type = "bezier",
    points = { { 0.3, -0.3 }, { 0, 1 } },
})

-- Progression linéaire réelle : vitesse régulière, sans accélération.
-- Remplace l'ancienne courbe « liner » définie avec (1,1) et (1,1).
hl.curve("linear", {
    type = "bezier",
    points = { { 0, 0 }, { 1, 1 } },
})

-- ============================================================================
-- 2. ANIMATIONS DES FENÊTRES
-- ============================================================================
-- speed : durée exprimée en dixièmes de seconde (6 = 0,6 seconde).
-- style = "slide" : effet de glissement lors de l'apparition/disparition.
-- Les sous-catégories remplacent les valeurs héritées de « windows ».

-- Réglages généraux des fenêtres (valeur de repli).
hl.animation({ leaf = "windows", enabled = true, speed = 6, bezier = "wind", style = "slide" })

-- Ouverture d'une fenêtre.
hl.animation({ leaf = "windowsIn", enabled = true, speed = 6, bezier = "winIn", style = "slide" })

-- Fermeture d'une fenêtre.
hl.animation({ leaf = "windowsOut", enabled = true, speed = 5, bezier = "winOut", style = "slide" })

-- Déplacement et redimensionnement d'une fenêtre.
hl.animation({ leaf = "windowsMove", enabled = true, speed = 5, bezier = "wind", style = "slide" })

-- ============================================================================
-- 3. BORDURES ET TRANSPARENCE
-- ============================================================================

-- Transition de couleur entre bordure active et inactive.
hl.animation({ leaf = "border", enabled = true, speed = 1, bezier = "linear" })

-- Animation de l'angle d'un dégradé de bordure.
-- « once » évite une animation permanente, plus coûteuse en ressources.
-- Elle n'est visible que si le thème utilise une bordure en dégradé.
hl.animation({ leaf = "borderangle", enabled = true, speed = 30, bezier = "linear", style = "once" })

-- Transitions d'opacité (apparition, disparition, etc.).
hl.animation({ leaf = "fade", enabled = true, speed = 10, bezier = "default" })

-- ============================================================================
-- 4. ESPACES DE TRAVAIL
-- ============================================================================

-- Transition entre les workspaces : conserve la courbe souple existante.
hl.animation({ leaf = "workspaces", enabled = true, speed = 5, bezier = "wind" })
