# -*- coding: utf-8 -*-
"""MCP-сервер «cbr-rates» по stdio (Работа C: MCP над курсами ЦБ РФ).

Файл: student_external.py. Сервер отдаёт данные через ТРИ инструмента:
list_rates, rate, convert (tickers не включён — по описанию работы C).

Требования работы C:
1. HTTP только через httpx с таймаутом; данные не импортируются из зеркала.
2. URL набора курсов задан прямо в коде сервера (константа CBR_XML_URL),
   а не берётся из переменных окружения.
3. XML парсится стандартной библиотекой xml.etree.ElementTree (get_data.py).
4. HTTP-ошибка, недоступность сервера или не-XML ответ -> ToolError,
   а не пустой список.
5. Неизвестный CharCode (rate("XXX")) -> ошибка.
6. convert учитывает Nominal (курс за номинал).
7. Кеш 30 минут (JSON-файл + память): повторные запросы в сеть не ходят.

Запуск (клиент из работ A/B подключается по stdio):
    python client.py student_external.py
    python client.py student_external.py rate '{"code":"AUD"}'
    python client.py student_external.py convert '{"amount":100,"from_code":"USD","to_code":"RUB"}'
"""
import asyncio

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import get_data

SERVER_NAME = "cbr-rates"
SERVER_VERSION = "1.0.0"

# Адрес набора курсов ЦБ: задан прямо в коде сервера, не из env.
CBR_XML_URL = "https://www.cbr-xml-daily.ru/daily_utf8.xml"


def _tool_error(exc: Exception) -> ToolError:
    return ToolError(str(exc))


def create_server() -> MCPServer:
    """Собрать MCP-сервер «cbr-rates» с инструментами list_rates/rate/convert."""
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        description=(
            "Курсы валют ЦБ РФ (зеркало cbr-xml-daily.ru): "
            "list_rates, rate, convert"
        ),
    )

    @server.tool(
        name="list_rates",
        description=(
            "Список курсов всех валют на дату набора. "
            "Результат: {date: ..., rates: [...]}, каждый rate — "
            "code, nominal, name, value (курс за номинал), rate (за 1 единицу)."
        ),
    )
    def list_rates() -> dict:
        try:
            return get_data.list_rates(url=CBR_XML_URL)
        except get_data.CbrRateError as exc:
            raise _tool_error(exc) from exc

    @server.tool(
        name="rate",
        description=(
            "Курс одной валюты по коду (CharCode), например AUD. "
            "Результат: code, nominal, name, value (курс за номинал), "
            "rate (за 1 единицу), date. Неизвестный код — ошибка."
        ),
    )
    def rate(code: str) -> dict:
        try:
            info = get_data.rate(code, to_rub=False, url=CBR_XML_URL)
        except get_data.CbrRateError as exc:
            raise _tool_error(exc) from exc
        return {
            "code": info["code"],
            "nominal": info["nominal"],
            "name": info["name"],
            "value": info["value"],
            "rate": info["rate"],
            "date": info["date"],
        }

    @server.tool(
        name="convert",
        description=(
            "Перевести amount из from_code в to_code. "
            "to_amount = amount * (from_rate/from_nominal) / (to_rate/to_nominal) — "
            "номинал учитывается у обеих валют; RUB — базовая валюта (курс 1). "
            "Результат: from_amount, from_rate, to_rate, to_amount, date."
        ),
    )
    def convert(amount: float, from_code: str, to_code: str) -> dict:
        try:
            return get_data.convert(amount, from_code, to_code, url=CBR_XML_URL)
        except get_data.CbrRateError as exc:
            raise _tool_error(exc) from exc

    return server


def main() -> None:
    """Точка входа: поднять сервер по stdio."""
    asyncio.run(create_server().run_stdio_async())


if __name__ == "__main__":
    main()