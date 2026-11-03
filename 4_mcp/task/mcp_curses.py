# -*- coding: utf-8 -*-
"""MCP-сервер «cbr-rates» по stdio (Работа C: MCP над курсами ЦБ РФ).

Файл: mcp_curses.py. Вся логика данных — в модуле get_data.py;
здесь только обвязка MCP (mcp SDK 2.x, transport: stdio).

Инструменты:
    list_rates()            -> {"date": ..., "rates": [...]}
    rate(code: str)         -> код, номинал, имя, курс, дата (неизвестный код — ошибка)
    convert(amount, from_code, to_code)
                            -> from_amount, from_rate, to_rate, to_amount, date
    tickers()               -> пары [CharCode, Name]

Любая ошибка данных (сеть/HTTP, не-XML, неизвестный код) превращается
в ToolError с понятным сообщением, а не в пустой список.
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
    """Сообщения CbrRateError уже человеко-читаемы — оборачиваем как есть."""
    return ToolError(str(exc))


def create_server(with_tickers: bool = True) -> MCPServer:
    """Собрать MCP-сервер с инструментами (tickers опционально)."""
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        description=(
            "Курсы валют ЦБ РФ (зеркало cbr-xml-daily.ru): "
            "list_rates, rate, convert" + (", tickers" if with_tickers else "")
        ),
    )

    @server.tool(
        name="list_rates",
        description=(
            "Список курсов всех валют на дату набора. "
            "Результат: {date: ..., rates: [...]}, каждый rate — "
            "code, num_code, nominal, name, value (курс за номинал), "
            "vunit_rate, rate (курс за 1 единицу)."
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
            "to_amount = amount * (from_rate/from_nominal) / (to_rate/to_nominal); "
            "номинал (Nominal) учитывается у обеих валют; RUB — базовая валюта "
            "(курс 1, номинал 1), её в списке нет, но конвертация с ней работает. "
            "Результат: from_amount, from_rate, to_rate, to_amount, date."
        ),
    )
    def convert(amount: float, from_code: str, to_code: str) -> dict:
        try:
            return get_data.convert(amount, from_code, to_code, url=CBR_XML_URL)
        except get_data.CbrRateError as exc:
            raise _tool_error(exc) from exc

    if with_tickers:

        @server.tool(
            name="tickers",
            description=(
                "Список доступных тикеров (CharCode): пары [код, название], "
                "например [\"HUF\", \"Венгерских форинтов\"]."
            ),
        )
        def tickers() -> list:
            try:
                return [list(pair) for pair in get_data.get_tickers(url=CBR_XML_URL)]
            except get_data.CbrRateError as exc:
                raise _tool_error(exc) from exc

    return server


def main() -> None:
    """Точка входа: поднять сервер по stdio."""
    asyncio.run(create_server().run_stdio_async())


if __name__ == "__main__":
    main()