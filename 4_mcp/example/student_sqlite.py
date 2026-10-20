"""Реализуйте четыре tools из задания. SQL пишется здесь, а не в клиенте."""
from mcp.server import MCPServer

mcp = MCPServer("student-shop-db")

# TODO: find_products(query, limit=10)
# TODO: get_order(order_id)
# TODO: customer_orders(customer_id)
# TODO: sales_summary(date_from, date_to)

if __name__ == "__main__":
    mcp.run(transport="stdio")
