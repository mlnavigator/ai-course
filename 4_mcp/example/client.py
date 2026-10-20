"""Список tools: python client.py SERVER.py
Вызов: python client.py SERVER.py TOOL_NAME '{"argument": 1}'
Вместо SERVER.py можно передать HTTP URL MCP-сервера.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("server")
    parser.add_argument("tool", nargs="?")
    parser.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()
    if args.server.startswith(("http://", "https://")):
        target = args.server
    else:
        target = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(args.server).resolve())],
            env=dict(os.environ),
        )
    async with Client(target) as client:
        if args.tool is None:
            result = await client.list_tools()
            output = [{"name": t.name, "description": t.description,
                       "input_schema": t.input_schema} for t in result.tools]
        else:
            result = await client.call_tool(args.tool, json.loads(args.arguments))
            output = {"is_error": result.is_error,
                      "structured_content": result.structured_content,
                      "content": [b.model_dump(mode="json", by_alias=True) for b in result.content]}
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
