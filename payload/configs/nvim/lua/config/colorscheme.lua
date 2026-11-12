
require("vscode").setup({
  style = "dark",
  transparent = false,
  italic_comments = true,
})

vim.cmd.colorscheme("vscode")

require("lualine").setup({
  options = {
    theme = "vscode",
    section_separators = "",
    component_separators = "",
  },
})
