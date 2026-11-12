-- Workspaces (written by the Quickshell display panel, ALT + D)
-- Entry N is the monitor workspace N lives on; the first workspace of each monitor is its default.

local assignment = {
	"eDP-1",
	"eDP-1",
	"eDP-1",
	"DP-9",
	"DP-9",
	"DP-9",
	"DP-9",
	"DP-9",
	"DP-6",
	"DP-6",
}

local seen = {}
for workspace, output in ipairs(assignment) do
	hl.workspace_rule({ workspace = tostring(workspace), monitor = output, default = not seen[output] })
	seen[output] = true
end

return assignment
