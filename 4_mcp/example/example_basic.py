from typing import Any
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("price-demo")


@mcp.tool()
def calculate_total(price_kopecks: int, quantity: int) -> dict[str, Any]:
    """Рассчитать стоимость покупки в копейках без скидок и доставки."""
    if price_kopecks < 0 or quantity < 1:
        raise ToolError("Цена должна быть неотрицательной, количество — не меньше 1")
    return {"total_kopecks": price_kopecks * quantity, "currency": "RUB"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
