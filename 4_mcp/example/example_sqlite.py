from typing import Any
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("sqlite-example")
DB = Path(os.getenv("SHOP_DB", Path(__file__).with_name("shop.db"))).resolve()


@mcp.tool()
def get_customer(customer_id: int) -> dict[str, Any]:
    """Получить имя и город клиента магазина по его ID."""
    if not DB.is_file():
        raise ToolError("Файл БД не найден: проверьте настройку SHOP_DB")
    with closing(sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, city FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        raise ToolError("Клиент не найден")
    return dict(row)


if __name__ == "__main__":
    mcp.run(transport="stdio")
