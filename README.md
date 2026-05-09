# toon-proxy

MCP stdio proxy that rewrites JSON tool outputs to [TOON](https://github.com/hackerhoon/python-toon) format.

## What it does

`toon-proxy` sits between an MCP client and server. It intercepts responses and:

- Converts JSON text content in `tools/call` responses to TOON format (tab-delimited, `#`-length-marked)
- Strips `outputSchema` from `tools/list` responses

The package ships two commands:

- `toon-proxy` — the proxy itself, used as the `command` for an MCP server entry
- `toon-proxy-wrap` — a helper that rewrites Claude Code MCP config files so every stdio server launches through `toon-proxy`

## Installation

Recommended (with [uv](https://github.com/astral-sh/uv)):

```bash
uv tool install git+https://github.com/hackerhoon/toon-proxy
```

This installs both `toon-proxy` and `toon-proxy-wrap` into `~/.local/bin/`. If that directory is not on your PATH yet:

```bash
uv tool update-shell
# then restart your shell
```

From a local clone:

```bash
uv tool install .
```

## Usage

### Wrap a single MCP server manually

In your MCP client config (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "fetch": {
      "command": "toon-proxy",
      "args": ["uvx", "mcp-server-fetch"]
    }
  }
}
```

Or invoke it directly:

```bash
toon-proxy uvx mcp-server-fetch
```

### Wrap every Claude Code stdio MCP server at once

Claude Code has no global setting for prepending a wrapper to MCP launches, so each stdio server's `command` has to point at `toon-proxy` with the original command shifted into `args`. `toon-proxy-wrap` automates that across config files.

```bash
# Preview the changes without writing
toon-proxy-wrap --dry-run

# Apply to ~/.claude.json (default target)
toon-proxy-wrap

# Apply to additional config files too
toon-proxy-wrap ~/.claude.json path/to/project/.mcp.json

# Restore the previous content from the auto-created backup
toon-proxy-wrap --restore
```

Behavior:

- Recursively walks every `mcpServers` mapping in the target file (covers both top-level and `projects.*` entries in `~/.claude.json`).
- Only touches stdio servers — entries with an `http` / `sse` transport or a `url` field are left alone.
- Resolves `toon-proxy` to an absolute path because MCP launchers do not inherit the interactive shell's PATH.
- Idempotent: re-running after adding a new server only wraps the new entries.
- Creates a one-time `<file>.toon-bak` backup on first mutation; `--restore` copies it back.

After running it, restart Claude Code so the MCP servers are spawned through `toon-proxy`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TOON_PROXY_LOG_PATH` | `toon-proxy.log` | Path to the log file |

## Requirements

- Python 3.10+
- [`python-toon`](https://github.com/hackerhoon/python-toon)
