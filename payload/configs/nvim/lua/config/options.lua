vim.loader.enable() -- Active le cache Lua pour accélérer le démarrage

vim.g.mapleader = " " -- Définit la touche leader (Space)
vim.g.maplocalleader = " " -- Leader local (souvent inutile mais bonne pratique)

vim.opt.number = true -- Affiche les numéros de ligne absolus
vim.opt.relativenumber = true -- Affiche les numéros relatifs (distance par rapport au curseur)
vim.opt.cursorline = true -- Met en surbrillance la ligne du curseur
vim.opt.signcolumn = "yes" -- Réserve toujours une colonne pour les signes (erreurs, git)
vim.opt.termguicolors = true -- Active les couleurs 24 bits (nécessaire pour les thèmes modernes)

vim.opt.tabstop = 2 -- Nombre d'espaces pour une tabulation affichée
vim.opt.shiftwidth = 2 -- Nombre d'espaces utilisés pour l'indentation
vim.opt.expandtab = true -- Convertit les tabulations en espaces
vim.opt.smartindent = true -- Active une indentation automatique intelligente

vim.opt.wrap = false -- Désactive le retour à la ligne automatique (scroll horizontal)
vim.opt.scrolloff = 8 -- Garde 8 lignes visibles autour du curseur (confort)
vim.opt.sidescrolloff = 8 -- Garde une marge horizontale lors du scroll

vim.opt.ignorecase = true -- Recherche insensible à la casse
vim.opt.smartcase = true -- Si majuscule utilisée → recherche sensible à la casse
vim.opt.hlsearch = true -- Met en surbrillance les résultats de recherche

vim.opt.clipboard = "unnamedplus" -- Utilise le presse-papiers système (copier/coller global)
vim.opt.mouse = "a" -- Active la souris dans tous les modes

vim.opt.updatetime = 200 -- Temps avant déclenchement de certains événements (LSP, etc.)
vim.opt.timeoutlen = 700 -- Temps d'attente pour les raccourcis (leader)

vim.opt.splitright = true -- Les splits verticaux s'ouvrent à droite
vim.opt.splitbelow = true -- Les splits horizontaux s'ouvrent en bas

vim.opt.undofile = true -- Active l'historique des modifications (undo persistant)
vim.opt.swapfile = false -- Désactive les fichiers swap (.swp)
vim.opt.backup = false -- Désactive les fichiers de sauvegarde
