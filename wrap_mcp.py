"""toon-proxy-wrap: rewrite Claude Code MCP configs to launch through toon-proxy.

Idempotently wraps every stdio MCP server's `command` so it goes through the
toon-proxy binary. Safe to re-run after adding new servers.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def find_toon_proxy() -> str:
    """Resolve an absolute path to the toon-proxy executable.

    MCP servers are launched without the user's interactive shell, so PATH may
    differ. Prefer an absolute path to avoid surprises.
    """
    candidate = shutil.which("toon-proxy")
    if candidate:
        return candidate
    # Common uv tool install location
    fallback = Path.home() / ".local" / "bin" / "toon-proxy"
    if fallback.exists():
        return str(fallback)
    sys.exit(
        "toon-proxy not found on PATH or at ~/.local/bin/toon-proxy. "
        "Install it first: uv tool install ~/Desktop/toon-proxy"
    )


def is_stdio_server(entry: dict) -> bool:
    """Heuristic: stdio MCP entries have a `command` field and no http/sse url."""
    if not isinstance(entry, dict):
        return False
    transport = entry.get("transport") or entry.get("type")
    if transport and transport not in ("stdio",):
        return False
    if "url" in entry:
        return False
    return isinstance(entry.get("command"), str)


def wrap_entry(entry: dict, proxy_path: str) -> bool:
    """Wrap a single MCP server entry. Returns True if mutated."""
    cmd = entry.get("command")
    args = entry.get("args") or []
    if cmd == proxy_path or (isinstance(cmd, str) and cmd.endswith("/toon-proxy")):
        return False  # already wrapped
    entry["command"] = proxy_path
    entry["args"] = [cmd, *args]
    return True


def walk_mcp_servers(node: Any, proxy_path: str, changed: list[str], path: str = "$") -> None:
    """Recursively find every `mcpServers` mapping and wrap stdio entries."""
    if isinstance(node, dict):
        servers = node.get("mcpServers")
        if isinstance(servers, dict):
            for name, entry in servers.items():
                if is_stdio_server(entry) and wrap_entry(entry, proxy_path):
                    changed.append(f"{path}.mcpServers.{name}")
        for k, v in node.items():
            walk_mcp_servers(v, proxy_path, changed, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_mcp_servers(v, proxy_path, changed, f"{path}[{i}]")


def process_file(path: Path, proxy_path: str, dry_run: bool) -> int:
    if not path.exists():
        print(f"skip (not found): {path}", file=sys.stderr)
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"skip (invalid json): {path}: {e}", file=sys.stderr)
        return 0

    changed: list[str] = []
    walk_mcp_servers(data, proxy_path, changed)

    if not changed:
        print(f"unchanged: {path}")
        return 0

    print(f"{'(dry) ' if dry_run else ''}wrap {len(changed)} server(s) in {path}:")
    for loc in changed:
        print(f"  - {loc}")

    if dry_run:
        return len(changed)

    backup = path.with_suffix(path.suffix + ".toon-bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"  backup -> {backup}")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(changed)


def restore_file(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".toon-bak")
    if not backup.exists():
        print(f"no backup for {path}", file=sys.stderr)
        return
    shutil.copy2(backup, path)
    print(f"restored {path} from {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="toon-proxy-wrap",
        description="Wrap Claude Code MCP stdio servers through toon-proxy.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Config files to process. Default: ~/.claude.json",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    parser.add_argument("--restore", action="store_true", help="Restore from .toon-bak files.")
    args = parser.parse_args()

    targets = [Path(p).expanduser() for p in args.files] or [Path.home() / ".claude.json"]

    if args.restore:
        for p in targets:
            restore_file(p)
        return

    proxy_path = find_toon_proxy()
    print(f"using toon-proxy: {proxy_path}")

    total = 0
    for p in targets:
        total += process_file(p, proxy_path, args.dry_run)
    print(f"{'(dry) ' if args.dry_run else ''}done. {total} server(s) {'would be ' if args.dry_run else ''}wrapped.")


if __name__ == "__main__":
    main()
