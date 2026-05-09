# toon-proxy

MCP stdio proxy that rewrites JSON tool outputs to [TOON](https://github.com/hackerhoon/python-toon) format.

## What it does

`toon-proxy` sits between an MCP client and server. It intercepts responses and:

- Converts JSON text content in `tools/call` responses to TOON format (tab-delimited, `#`-length-marked)
- Strips `outputSchema` from `tools/list` responses

## Installation

```bash
pip install toon-proxy
```

Or from source:

```bash
pip install .
```

## Usage

Wrap any MCP server command with `toon-proxy`:

```bash
toon-proxy <command> [args...]
```

### Example

```bash
toon-proxy uvx mcp-server-fetch
```

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

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TOON_PROXY_LOG_PATH` | `toon-proxy.log` | Path to the log file |

## Requirements

- Python 3.10+
- [`python-toon`](https://github.com/hackerhoon/python-toon)

## Contributors

- [@hackerhoon](https://github.com/hackerhoon)
- [Claude Opus 4.7](https://www.anthropic.com/claude) — AI pair programmer
