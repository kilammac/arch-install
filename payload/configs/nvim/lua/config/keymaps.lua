local map = vim.keymap.set

-- =========================
-- BASE
-- =========================

vim.g.mapleader = " "

map("n", "<leader>w", "<cmd>w<cr>", { desc = "Sauvegarder" })
map("n", "<leader>q", "<cmd>q<cr>", { desc = "Quitter" })
map("n", "<leader>Q", "<cmd>qa!<cr>", { desc = "Quitter tout sans sauvegarder" })

map("n", "<C-s>", "<cmd>w<cr>", { desc = "Sauvegarder (rapide)" })

-- =========================
-- EXPLORATEUR (oil)
-- =========================

map("n", "-", "<cmd>Oil<cr>", { desc = "Ouvrir le dossier parent" })

-- =========================
-- BUFFERS
-- =========================

map("n", "<leader>bd", "<cmd>bdelete<cr>", { desc = "Fermer le buffer" })
map("n", "<S-l>", "<cmd>bnext<cr>", { desc = "Buffer suivant" })
map("n", "<S-h>", "<cmd>bprevious<cr>", { desc = "Buffer précédent" })

-- =========================
-- NAVIGATION FENÊTRES
-- =========================

map("n", "<C-h>", "<C-w>h", { desc = "Aller à la fenêtre gauche" })
map("n", "<C-j>", "<C-w>j", { desc = "Aller à la fenêtre du bas" })
map("n", "<C-k>", "<C-w>k", { desc = "Aller à la fenêtre du haut" })
map("n", "<C-l>", "<C-w>l", { desc = "Aller à la fenêtre droite" })

map("n", "<leader>sv", "<cmd>vsplit<cr>", { desc = "Split vertical" })
map("n", "<leader>sh", "<cmd>split<cr>", { desc = "Split horizontal" })
map("n", "<leader>sx", "<cmd>close<cr>", { desc = "Fermer la fenêtre" })

-- =========================
-- DÉPLACER LIGNES
-- =========================

map("n", "<A-j>", ":m .+1<cr>==", { desc = "Déplacer la ligne vers le bas" })
map("n", "<A-k>", ":m .-2<cr>==", { desc = "Déplacer la ligne vers le haut" })

map("v", "<A-j>", ":m '>+1<cr>gv=gv", { desc = "Déplacer la sélection vers le bas" })
map("v", "<A-k>", ":m '<-2<cr>gv=gv", { desc = "Déplacer la sélection vers le haut" })

-- =========================
-- RECHERCHE (Telescope)
-- =========================

map("n", "<leader>ff", function()
	require("telescope.builtin").find_files()
end, { desc = "Rechercher un fichier" })

map("n", "<leader>fg", function()
	require("telescope.builtin").live_grep()
end, { desc = "Rechercher du texte dans le projet" })

map("n", "<leader>fb", function()
	require("telescope.builtin").buffers()
end, { desc = "Rechercher un buffer ouvert" })

map("n", "<leader>fh", function()
	require("telescope.builtin").help_tags()
end, { desc = "Rechercher dans l'aide" })

-- =========================
-- LSP (langage)
-- =========================

map("n", "gd", vim.lsp.buf.definition, { desc = "Aller à la définition" })
map("n", "gD", vim.lsp.buf.declaration, { desc = "Aller à la déclaration" })
map("n", "gr", vim.lsp.buf.references, { desc = "Afficher les références" })
map("n", "gi", vim.lsp.buf.implementation, { desc = "Aller à l’implémentation" })
map("n", "K", vim.lsp.buf.hover, { desc = "Afficher la documentation" })

map("n", "<leader>rn", vim.lsp.buf.rename, { desc = "Renommer le symbole" })
map("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "Action de code" })

-- =========================
-- DIAGNOSTICS (erreurs)
-- =========================

map("n", "[d", vim.diagnostic.goto_prev, { desc = "Erreur précédente" })
map("n", "]d", vim.diagnostic.goto_next, { desc = "Erreur suivante" })

map("n", "<leader>e", vim.diagnostic.open_float, { desc = "Afficher l’erreur" })
map("n", "<leader>dl", vim.diagnostic.setloclist, { desc = "Liste des diagnostics" })

-- =========================
-- FORMATAGE
-- =========================

map("n", "<leader>f", function()
	require("conform").format({ async = true })
end, { desc = "Formatter le fichier" })

-- =========================
-- TERMINAL
-- =========================

map("n", "<leader>tt", "<cmd>terminal<cr>", { desc = "Ouvrir un terminal" })
map("t", "<esc>", [[<C-\><C-n>]], { desc = "Quitter le mode terminal" })

-- =========================
-- FERMETURE RAPIDE
-- =========================

map("n", "<leader>x", "<cmd>close<cr>", { desc = "Fermer la fenêtre actuelle" })
