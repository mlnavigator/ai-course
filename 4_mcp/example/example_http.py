from typing import Any
import os

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("delivery-health-example")
API_URL = os.getenv("DELIVERY_API_URL", "http://127.0.0.1:8000").rstrip("/")


@mcp.tool()
async def delivery_health() -> dict[str, Any]:
    """Проверить доступность API доставки. Не проверяет состояние конкретного заказа."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_URL}/health")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise ToolError(f"API вернул HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ToolError("API доставки недоступен или не ответил вовремя") from exc
    except ValueError as exc:
        raise ToolError("API вернул ответ не в формате JSON") from exc


if __name__ == "__main__":
    mcp.run(transport="stdio")
