"""toon-proxy: MCP stdio proxy that rewrites JSON tool outputs to TOON."""

import json
import logging
import os
import subprocess
import sys
import threading
from typing import Any

from toon import encode


def setup_logger() -> logging.Logger:
    log_path = os.environ.get("TOON_PROXY_LOG_PATH", "toon-proxy.log")
    logger = logging.getLogger("toon-proxy")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, mode="w")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def json_to_toon(data: str) -> str:
    s = data.strip()
    if not s or s[0] not in "{[":
        return data
    parsed = json.loads(s)
    return encode(parsed, {"delimiter": "\t", "lengthMarker": "#"})


def convert_tool_call(msg: dict, logger: logging.Logger) -> dict:
    result = msg.get("result")
    if not isinstance(result, dict):
        return msg

    contents = result.get("content")
    if not isinstance(contents, list):
        return msg

    if "structuredContent" in result and contents:
        result.pop("structuredContent", None)

    for item in contents:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            item["text"] = json_to_toon(text)
        except Exception as e:
            logger.info("convert error: %s", e)
    return msg


def strip_output_schemas(msg: dict) -> dict:
    result = msg.get("result")
    if not isinstance(result, dict):
        return msg
    tools = result.get("tools")
    if not isinstance(tools, list):
        return msg
    for tool in tools:
        if isinstance(tool, dict):
            tool.pop("outputSchema", None)
    return msg


def main() -> None:
    if len(sys.argv) <= 1:
        print("Usage: toon-proxy <command> [args...]", file=sys.stderr)
        sys.exit(1)

    logger = setup_logger()

    proc = subprocess.Popen(
        sys.argv[1:],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    call_ids: set[str] = set()
    list_ids: set[str] = set()
    lock = threading.Lock()

    def client_to_server() -> None:
        try:
            for raw in sys.stdin.buffer:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                try:
                    msg = json.loads(line)
                    method = msg.get("method")
                    msg_id = msg.get("id")
                    if msg_id is not None:
                        key = str(msg_id)
                        with lock:
                            if method == "tools/call":
                                call_ids.add(key)
                            elif method == "tools/list":
                                list_ids.add(key)
                except Exception as e:
                    logger.info("client parse error: %s", e)
                logger.info(">>> %s", line)
                proc.stdin.write((line + "\n").encode("utf-8"))
                proc.stdin.flush()
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    def server_to_client() -> None:
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            out_line = line
            try:
                msg = json.loads(line)
                msg_id = msg.get("id")
                if msg_id is not None:
                    key = str(msg_id)
                    with lock:
                        is_call = key in call_ids
                        is_list = key in list_ids
                        call_ids.discard(key)
                        list_ids.discard(key)
                    if is_call:
                        msg = convert_tool_call(msg, logger)
                    if is_list:
                        msg = strip_output_schemas(msg)
                    if is_call or is_list:
                        out_line = json.dumps(msg, ensure_ascii=False)
            except Exception as e:
                logger.info("server parse error: %s", e)
            logger.info("<<< %s", out_line)
            sys.stdout.write(out_line + "\n")
            sys.stdout.flush()

    def server_stderr() -> None:
        for raw in proc.stderr:
            logger.info("ERR %s", raw.decode("utf-8", errors="replace").rstrip())

    threads = [
        threading.Thread(target=client_to_server, daemon=True),
        threading.Thread(target=server_to_client, daemon=True),
        threading.Thread(target=server_stderr, daemon=True),
    ]
    for t in threads:
        t.start()

    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
