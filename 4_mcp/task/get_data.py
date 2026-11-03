# -*- coding: utf-8 -*-
"""Загрузка и парсинг курсов ЦБ РФ (Работа C, MCP над курсами ЦБ).

Источник — зеркало курсов ЦБ в UTF-8: https://www.cbr-xml-daily.ru/daily_utf8.xml
(тот же формат XML_daily.asp, но в UTF-8; официальный файл ЦБ — в cp1251).

URL НЕ берётся из переменных окружения: адрес набора задан прямо в коде
MCP-сервера (константа CBR_XML_URL в student_external.py / mcp_curses.py),
по умолчанию — DEFAULT_XML_URL. Любая функция принимает необязательный
аргумент url, чтобы вызывающая сторона (сервер) могла явно указать адрес.

Правила модуля:
* HTTP — только через `httpx` c обязательным таймаутом.
* XML — стандартная библиотека `xml.etree.ElementTree`.
* `Value` — строка с запятой («57,7882») -> число 57.7882 (запятая -> точка).
* `Nominal` — курс задан ЗА указанный номинал (у JPY — 100), не за единицу.
* RUB в наборе нет — это базовая валюта: везде обрабатывается как курс 1
  за номинал 1 (выбрано «поддерживать», а не «явно запрещать»).
* Кеш — JSON-файл со свежестью 30 минут + in-memory кеш процесса:
  повторные запросы в сеть не ходят (данные обновляются раз в день).

Ошибки: FetchError (сеть/HTTP), ParseError (не XML), CurrencyNotFoundError
(неизвестный CharCode) — все наследуют CbrRateError.
"""
import json
import os
import time
import xml.etree.ElementTree as ET

import httpx

# Базовый адрес XML-файла курсов (задан в коде, не из env).
DEFAULT_XML_URL = "https://www.cbr-xml-daily.ru/daily_utf8.xml"
DEFAULT_TIMEOUT = 10.0  # секунд — таймаут обязателен по условию
CACHE_TTL_SECONDS = 30 * 60  # 30 минут: данные ЦБ обновляются раз в день
DEFAULT_CACHE_FILE = ".cbr_rates_cache.json"

# RUB — базовая валюта: её нет в списке <Valute>, курс 1 за номинал 1.
_RUB_INFO = {
    "code": "RUB",
    "num_code": "643",
    "nominal": 1,
    "name": "Российский рубль",
    "value": 1.0,
    "vunit_rate": 1.0,
}

_memory_cache = None  # in-memory снапшот {"date", "rates", "timestamp"}


class CbrRateError(Exception):
    """Базовая ошибка модуля get_data."""


class FetchError(CbrRateError):
    """Сеть/HTTP: сервер недоступен, таймаут, ответ не HTTP 200."""


class ParseError(CbrRateError):
    """Ответ не является корректным XML <ValCurs>."""


class CurrencyNotFoundError(CbrRateError, ValueError):
    """Неизвестный код валюты (CharCode), например rate("XXX")."""


def xml_url() -> str:
    """Адрес XML-файла курсов (константа, заданная в коде)."""
    return DEFAULT_XML_URL


def cache_file() -> str:
    """Путь к JSON-файлу кеша (CBR_CACHE_FILE, по умолчанию локальный)."""
    return os.environ.get("CBR_CACHE_FILE", DEFAULT_CACHE_FILE)


# ---------------------------------------------------------------------------
# Слой скачивания и парсинга
# ---------------------------------------------------------------------------

def fetch_xml(url=None, timeout=DEFAULT_TIMEOUT) -> str:
    """Скачать XML курсов через httpx.get (обязательный таймаут).

    url: адрес набора; по умолчанию DEFAULT_XML_URL.
    HTTP-ошибка, недоступность сервера или таймаут -> FetchError,
    а не пустой список.
    """
    target = url or DEFAULT_XML_URL
    try:
        response = httpx.get(target, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise FetchError(
            f"Не удалось загрузить курсы ЦБ ({target}): {exc}"
        ) from exc
    if response.status_code != 200:
        raise FetchError(
            f"При загрузке курсов ЦБ ({target}) сервер вернул HTTP "
            f"{response.status_code}"
        )
    return response.text


def parse_xml(text: str) -> dict:
    """Разобрать XML <ValCurs> в {"date": ..., "rates": [...]}.

    rates — список словарей: code, num_code, nominal, name, value, vunit_rate.
    "value" — курс ЗА номинал (запятая -> точка), "rate" добавляется позже.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ParseError(f"Ответ не является корректным XML: {exc}") from exc

    if root.tag != "ValCurs":
        raise ParseError(
            f"Неожиданный корневой элемент <{root.tag}>, ожидался <ValCurs>"
        )

    rates = []
    for node in root.findall("Valute"):
        nominal = int(node.findtext("Nominal") or "1")
        value = float((node.findtext("Value") or "0").replace(",", "."))
        vunit = float((node.findtext("VunitRate") or "0").replace(",", "."))
        rates.append({
            "code": node.findtext("CharCode") or "",
            "num_code": node.findtext("NumCode") or "",
            "nominal": nominal,
            "name": node.findtext("Name") or "",
            "value": value,          # рублей за `nominal` единиц валюты
            "vunit_rate": vunit,
            "rate": value / nominal if nominal else 0.0,  # рублей за 1 единицу
        })

    if not rates:
        raise ParseError("В ответе не найдено ни одного элемента <Valute>")

    return {"date": root.get("Date") or "", "rates": rates}


# ---------------------------------------------------------------------------
# Кеш (JSON-файл + память), 30 минут
# ---------------------------------------------------------------------------

def _build_snapshot(text: str) -> dict:
    """Снапшот из XML: {"date", "rates", "timestamp"}."""
    snap = parse_xml(text)
    snap["timestamp"] = time.time()
    return snap


def _write_cache(snapshot: dict) -> None:
    """Сбросить снапшот в JSON-файл (best-effort: кеш не критичен)."""
    try:
        with open(cache_file(), "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False)
    except OSError:
        pass


def _read_cache() -> dict:
    """Прочитать свежий снапшот из JSON-файла или вернуть None."""
    try:
        with open(cache_file(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "timestamp" not in data:
        return None
    if time.time() - data["timestamp"] > CACHE_TTL_SECONDS:
        return None
    return data


def _fresh_snapshot() -> dict:
    """Свежий снапшот (память -> файл) или None."""
    global _memory_cache
    if _memory_cache is not None:
        if time.time() - _memory_cache["timestamp"] <= CACHE_TTL_SECONDS:
            return _memory_cache
        _memory_cache = None
    cached = _read_cache()
    if cached is not None:
        _memory_cache = cached
        return cached
    return None


# ---------------------------------------------------------------------------
# Публичное API
# ---------------------------------------------------------------------------

def get_data(url=None) -> dict:
    """Скачать и распарсить XML, сложить результат в JSON (с timestamp) и отдать.

    url: адрес набора (обычно задаётся MCP-сервером); по умолчанию DEFAULT_XML_URL.
    Возвращает снапшот: {"date", "rates", "timestamp"}.
    Ошибки сети/парсинга пробрасываются как FetchError/ParseError.
    """
    global _memory_cache
    snapshot = _build_snapshot(fetch_xml(url))
    _memory_cache = snapshot
    _write_cache(snapshot)
    return snapshot


def _snapshot(url=None) -> dict:
    """Актуальный снапшот: свежий кеш или новое скачивание (с url)."""
    return _fresh_snapshot() or get_data(url)


def list_rates(url=None) -> dict:
    """Курсы валют на дату: {"date": ..., "rates": [...]}.

    Если кеш свежее 30 минут — берём его (без сети), иначе обновляем.
    """
    snap = _snapshot(url)
    return {"date": snap["date"], "rates": snap["rates"]}


def get_tickers(url=None) -> list:
    """Список доступных тикеров: [(CharCode, Name), ...]."""
    return [(r["code"], r["name"]) for r in _snapshot(url)["rates"]]


def validate(ticker: str, url=None) -> bool:
    """Есть ли тикер в наборе (RUB — базовая валюта — всегда доступен)."""
    code = ticker.strip().upper()
    if code == "RUB":
        return True
    return any(r["code"].upper() == code for r in _snapshot(url)["rates"])


def _find_rate(ticker: str, url=None) -> dict:
    """Словарь валюты по коду (RUB -> базовая запись). Ошибка, если нет."""
    code = ticker.strip().upper()
    if code == "RUB":
        return dict(_RUB_INFO)
    for r in _snapshot(url)["rates"]:
        if r["code"].upper() == code:
            return r
    raise CurrencyNotFoundError(f"Неизвестный код валюты: {ticker}")


def rate(ticker: str, to_rub: bool = False, url=None) -> dict:
    """Курс валюты.

    to_rub=False: "rate" — рублей за 1 единицу валюты (value / nominal).
    to_rub=True:  "rate" — единиц валюты за 1 рубль (nominal / value).
    RUB — базовая валюта, курс 1 в обе стороны.
    """
    info = _find_rate(ticker, url)
    per_unit = info["value"] / info["nominal"]
    rate_value = 1.0 / per_unit if to_rub else per_unit
    return {
        "code": info["code"],
        "name": info["name"],
        "nominal": info["nominal"],
        "value": info["value"],
        "rate": rate_value,
        "to_rub": to_rub,
        "date": _snapshot(url)["date"],
    }


def convert(amount, from_code: str, to_code: str, url=None) -> dict:
    """Перевести amount из from_code в to_code.

    to_amount = amount * (from_rate / from_nominal) / (to_rate / to_nominal)
    — номинал (Nominal) учитывается у обеих валют; RUB = курс 1, номинал 1.
    """
    from_info = _find_rate(from_code, url)
    to_info = _find_rate(to_code, url)
    from_per_unit = from_info["value"] / from_info["nominal"]
    to_per_unit = to_info["value"] / to_info["nominal"]
    to_amount = amount * from_per_unit / to_per_unit
    return {
        "from_amount": amount,
        "from_rate": from_per_unit,
        "to_rate": to_per_unit,
        "to_amount": to_amount,
        "date": _snapshot(url)["date"],
    }