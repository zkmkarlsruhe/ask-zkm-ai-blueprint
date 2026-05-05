"""hello-world MCP — the smallest useful starting point.

Two tools. Replace them with real ones. Rename the package. Done.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from fastmcp import FastMCP

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

mcp = FastMCP(
    "hello-world",
    instructions=(
        "Demo MCP server. "
        "Use 'echo' to test that tool calls reach the server. "
        "Use 'now' to get the current UTC time."
    ),
)


@mcp.tool()
def echo(message: str) -> dict:
    """Return the message you sent. Useful for connectivity testing.

    Args:
        message: Any string. Will be returned verbatim.
    """
    return {"echoed": message}


@mcp.tool()
def now() -> dict:
    """Return the current UTC time in ISO 8601 format."""
    return {"utc": datetime.now(timezone.utc).isoformat()}


def main() -> None:
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
