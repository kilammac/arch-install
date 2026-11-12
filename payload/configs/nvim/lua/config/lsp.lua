local capabilities = vim.lsp.protocol.make_client_capabilities()

pcall(function()
  capabilities = require("cmp_nvim_lsp").default_capabilities(capabilities)
end)

-- Configuration globale appliquée à tous les serveurs
vim.lsp.config("*", {
  capabilities = capabilities,
})

-- Lua
vim.lsp.config("lua_ls", {
  settings = {
    Lua = {
      runtime = {
        version = "LuaJIT",
      },
      diagnostics = {
        globals = { "vim" },
      },
      workspace = {
        checkThirdParty = false,
        library = {
          vim.env.VIMRUNTIME,
          "${3rd}/luv/library",
        },
      },
      telemetry = {
        enable = false,
      },
    },
  },
})

-- Python
vim.lsp.config("pyright", {})

-- JavaScript / TypeScript / Next.js
vim.lsp.config("ts_ls", {})

-- ESLint
vim.lsp.config("eslint", {})

-- HTML / CSS / JSON
vim.lsp.config("html", {})
vim.lsp.config("cssls", {})
vim.lsp.config("jsonls", {})

-- Tailwind CSS
vim.lsp.config("tailwindcss", {})

-- Bash
vim.lsp.config("bashls", {})

-- Rust
vim.lsp.config("rust_analyzer", {
  settings = {
    ["rust-analyzer"] = {
      cargo = {
        allFeatures = true,
      },
      check = {
        command = "clippy",
      },
    },
  },
})

-- C / C++ / Arduino éventuel
vim.lsp.config("clangd", {})

-- Docker / Podman
vim.lsp.config("dockerls", {})
vim.lsp.config("docker_compose_language_service", {})

-- Markdown
vim.lsp.config("marksman", {})

-- PHP
vim.lsp.config("intelephense", {})

-- YAML
vim.lsp.config("yamlls", {})

-- Flutter / Dart
vim.lsp.config("dartls", {})

vim.lsp.enable({
  "lua_ls",
  "pyright",
  "ts_ls",
  "eslint",
  "html",
  "cssls",
  "jsonls",
  "tailwindcss",
  "bashls",
  "rust_analyzer",
  "clangd",
  "dockerls",
  "docker_compose_language_service",
  "marksman",
  "intelephense",
  "yamlls",
  "dartls",
})

-- Raccourcis LSP seulement quand un LSP est attaché
vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(event)
    local bufnr = event.buf
    local map = vim.keymap.set

    map("n", "gd", vim.lsp.buf.definition, { buffer = bufnr, desc = "Aller définition" })
    map("n", "gD", vim.lsp.buf.declaration, { buffer = bufnr, desc = "Aller déclaration" })
    map("n", "gr", vim.lsp.buf.references, { buffer = bufnr, desc = "Références" })
    map("n", "gi", vim.lsp.buf.implementation, { buffer = bufnr, desc = "Implémentation" })
    map("n", "K", vim.lsp.buf.hover, { buffer = bufnr, desc = "Documentation" })

    map("n", "<F2>", vim.lsp.buf.rename, { buffer = bufnr, desc = "Renommer" })
    map("n", "<F4>", vim.lsp.buf.code_action, { buffer = bufnr, desc = "Code action" })

    map("n", "<leader>lf", function()
      vim.lsp.buf.format({ async = true })
    end, { buffer = bufnr, desc = "Format LSP" })
  end,
})

vim.diagnostic.config({
  virtual_text = true,
  signs = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
})
