local builtin = require('telescope.builtin')
vim.keymap.set('n', '<leader>ff', builtin.find_files, {})
vim.keymap.set('n', '<leader>fg', builtin.live_grep, {})
vim.keymap.set('n', '<leader>fb', builtin.buffers, {})
vim.keymap.set('n', '<leader>fh', builtin.help_tags, {})

vim.keymap.set('i', 'kj', '<ESC>')
vim.keymap.set('n', '<leader>e', function () vim.cmd (":Explore") end, {})
vim.keymap.set('n', '<leader>es', function () vim.cmd (":Sexplore") end, {})
vim.keymap.set('n', '<leader>ev', function () vim.cmd (":Vexplore") end, {})

vim.cmd([[cabbrev help tab help]])
vim.cmd([[
cnoreabbrev W! w!
cnoreabbrev W1 w!
cnoreabbrev w1 w!
cnoreabbrev Q! q!
cnoreabbrev Q1 q!
cnoreabbrev q1 q!
cnoreabbrev Qa! qa!
cnoreabbrev Qall! qall!
cnoreabbrev Wa wa
cnoreabbrev Wq wq
cnoreabbrev wQ wq
cnoreabbrev WQ wq
cnoreabbrev wq1 wq!
cnoreabbrev Wq1 wq!
cnoreabbrev wQ1 wq!
cnoreabbrev WQ1 wq!
cnoreabbrev W w
cnoreabbrev Q q
cnoreabbrev Qa qa
cnoreabbrev Qall qall
]])

-- Haskell tools
local ht = require('haskell-tools')
local bufnr = vim.api.nvim_get_current_buf()
local opts = { noremap = true, silent = true, buffer = bufnr, }
vim.keymap.set('n', '<space>cl', vim.lsp.codelens.run, opts)
vim.keymap.set('n', '<space>hs', ht.hoogle.hoogle_signature, opts)
vim.keymap.set('n', '<space>ea', ht.lsp.buf_eval_all, opts)
vim.keymap.set('n', '<leader>rr', ht.repl.toggle, opts)
vim.keymap.set('n', '<leader>rf', function() ht.repl.toggle(vim.api.nvim_buf_get_name(0)) end, opts)
vim.keymap.set('n', '<leader>rq', ht.repl.quit, opts)
