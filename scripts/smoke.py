"""Prueba de humo: arranca el servidor por stdio y llama a un par de herramientas.

    uv run --with mcp python scripts/smoke.py [proyecto]

Necesita VIKUNJA_URL y VIKUNJA_TOKEN en el entorno.
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    project = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VIKUNJA_PROJECT")
    params = StdioServerParameters(command="uv", args=["run", "vikunja-mcp"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", ", ".join(t.name for t in tools.tools))
            result = await session.call_tool("list_projects", {})
            print("projects:", result.content[0].text[:300])
            if project:
                result = await session.call_tool("list_tasks", {"project": project})
                data = json.loads(result.content[0].text)
                print(f"{data['project']['title']}: {len(data['tasks'])} tareas pendientes")
                for t in data["tasks"][:3]:
                    print(f"  #{t['id']} {t['title']}")


asyncio.run(main())
