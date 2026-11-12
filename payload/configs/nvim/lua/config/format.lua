require("conform").setup({
  formatters_by_ft = {
    lua = { "stylua" },

    python = { "isort", "black" },

    javascript = { "prettier", stop_after_first = true },
    javascriptreact = { "prettier", stop_after_first = true },
    typescript = { "prettier", stop_after_first = true },
    typescriptreact = { "prettier", stop_after_first = true },

    html = { "prettier", stop_after_first = true },
    css = { "prettier", stop_after_first = true },
    json = { "prettier", stop_after_first = true },
    yaml = { "prettier", stop_after_first = true },
    markdown = { "prettier", stop_after_first = true },

    sh = { "shfmt" },
    bash = { "shfmt" },

    rust = { "rustfmt", lsp_format = "fallback" },

    php = { lsp_format = "fallback" },
    dart = { lsp_format = "fallback" },
  },

  format_on_save = {
    timeout_ms = 800,
    lsp_format = "fallback",
  },
})
