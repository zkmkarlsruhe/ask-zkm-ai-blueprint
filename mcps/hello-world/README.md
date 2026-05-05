# hello-world MCP

The smallest useful FastMCP server. Two tools (`echo`, `now`). Copy this
folder, rename, and replace the tools with real ones to build your own.

## Run locally

```bash
docker compose up -d
curl http://localhost:8001/mcp     # should respond
```

## Wire to OpenWebUI

If OWUI runs on the same docker host, add `hello-world` to OWUI's network so
they can talk by service name:

```bash
docker network connect webui_backend hello-world
```

Then in OWUI: **Settings → Tools → "+"** with URL
`http://hello-world:8000/mcp`.

## Use this as your starter

```bash
cp -r hello-world/ ../my-mcp/
cd ../my-mcp/
# Rename the package
mv src/hello_world.py src/my_mcp.py
$EDITOR pyproject.toml          # rename project, scripts entry
$EDITOR src/my_mcp.py           # add your tools
```

The pattern is: each `@mcp.tool()` becomes a function the LLM can call. The
docstring becomes the tool description the model sees. Type hints become the
parameter schema.
