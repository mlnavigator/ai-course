"""Реализуйте четыре tools из задания. Обращайтесь к API только по HTTP."""
from mcp.server import MCPServer

mcp = MCPServer("student-delivery-api")

# TODO: list_deliveries(status=None)
# TODO: get_delivery(order_id)
# TODO: quote_delivery(weight_grams, zone)
# TODO: reschedule_delivery(order_id, planned_date)

if __name__ == "__main__":
    mcp.run(transport="stdio")
