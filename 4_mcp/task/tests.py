# -*- coding: utf-8 -*-
"""Тесты на модуль get_data (TDD, Работа C: курсы ЦБ РФ).

Сеть в тестах не используется: HTTP подменяется через monkeypatch на httpx.get,
а файловый кеш пишется во временную директорию tmp_path.
"""
import json
import time

import httpx
import pytest

import get_data
from get_data import (
    CurrencyNotFoundError,
    FetchError,
    ParseError,
    convert,
    get_data as _get_data,
    get_tickers,
    list_rates,
    parse_xml,
    rate,
    validate,
)

XML_DATE = "20.10.2026"

XML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<ValCurs Date="{date}" name="Foreign Currency Market">
  <Valute ID="R01010">
    <NumCode>036</NumCode><CharCode>AUD</CharCode>
    <Nominal>1</Nominal><Name>Австралийский доллар</Name>
    <Value>57,7882</Value><VunitRate>57,7882</VunitRate>
  </Valute>
  <Valute ID="R01235">
    <NumCode>840</NumCode><CharCode>USD</CharCode>
    <Nominal>1</Nominal><Name>Доллар США</Name>
    <Value>82,8504</Value><VunitRate>82,8504</VunitRate>
  </Valute>
  <Valute ID="R01820">
    <NumCode>392</NumCode><CharCode>JPY</CharCode>
    <Nominal>100</Nominal><Name>Иен</Name>
    <Value>52,4668</Value><VunitRate>0,5247</VunitRate>
  </Valute>
  <Valute ID="R01215">
    <NumCode>978</NumCode><CharCode>EUR</CharCode>
    <Nominal>1</Nominal><Name>Евро</Name>
    <Value>92,3</Value><VunitRate>92,3</VunitRate>
  </Valute>
</ValCurs>
""".format(date=XML_DATE)


@pytest.fixture(autouse=True)
def isolate_caches(monkeypatch, tmp_path):
    """Сбрасываем кеши и переносим файловый кеш во временную директорию."""
    monkeypatch.setattr(get_data, "_memory_cache", None)
    monkeypatch.setattr(
        get_data, "cache_file", lambda: str(tmp_path / "cbr_rates_cache.json")
    )
    yield


def make_fake_get(text=XML_SAMPLE, status_code=200, exc=None):
    """Фейковый httpx.get: либо бросает исключение, либо отвечает XML."""
    def fake_get(url, **kwargs):
        if exc is not None:
            raise exc
        return httpx.Response(
            status_code, text=text, request=httpx.Request("GET", url)
        )
    return fake_get


def seed_fresh_cache(monkeypatch):
    """Скачиваем (подменённым HTTP) и пишем свежий кеш через публичный get_data()."""
    monkeypatch.setattr(httpx, "get", make_fake_get())
    return _get_data()


def write_stale_cache(monkeypatch, tmp_path, age_seconds=60 * 60):
    """Пишем в файловый кеш снапшот с просроченным timestamp."""
    snap = get_data._build_snapshot(XML_SAMPLE)
    snap["timestamp"] = time.time() - age_seconds
    get_data._write_cache(snap)
    get_data._memory_cache = None


# ---------------------------------------------------------------------------
# parse_xml
# ---------------------------------------------------------------------------

def test_parse_xml_returns_date_and_rates():
    parsed = parse_xml(XML_SAMPLE)
    assert parsed["date"] == XML_DATE
    assert isinstance(parsed["rates"], list)
    assert len(parsed["rates"]) == 4


def test_parse_xml_rate_fields():
    parsed = parse_xml(XML_SAMPLE)
    rate_usd = next(r for r in parsed["rates"] if r["code"] == "USD")
    assert rate_usd["code"] == "USD"
    assert rate_usd["name"] == "Доллар США"
    assert rate_usd["nominal"] == 1
    assert rate_usd["value"] == pytest.approx(82.8504)


def test_parse_xml_comma_is_decimal_separator():
    """Value '57,7882' (запятая) должен стать числом 57.7882."""
    parsed = parse_xml(XML_SAMPLE)
    aud = next(r for r in parsed["rates"] if r["code"] == "AUD")
    assert isinstance(aud["value"], float)
    assert aud["value"] == pytest.approx(57.7882)


def test_parse_xml_jpy_nominal_is_100():
    parsed = parse_xml(XML_SAMPLE)
    jpy = next(r for r in parsed["rates"] if r["code"] == "JPY")
    assert jpy["nominal"] == 100
    assert jpy["value"] == pytest.approx(52.4668)


def test_parse_xml_vunit_rate():
    parsed = parse_xml(XML_SAMPLE)
    jpy = next(r for r in parsed["rates"] if r["code"] == "JPY")
    assert jpy["vunit_rate"] == pytest.approx(0.5247)


def test_parse_xml_not_xml_raises_parse_error():
    with pytest.raises(ParseError):
        parse_xml("<html>not a valcurs</html>")


def test_parse_xml_empty_valcurs_raises_parse_error():
    with pytest.raises(ParseError):
        parse_xml('<ValCurs Date="20.10.2026"></ValCurs>')


# ---------------------------------------------------------------------------
# fetch_xml (через httpx.get)
# ---------------------------------------------------------------------------

def test_fetch_xml_success(monkeypatch):
    monkeypatch.setattr(httpx, "get", make_fake_get())
    text = get_data.fetch_xml()
    assert "<ValCurs" in text


def test_fetch_xml_http_error_raises_fetch_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", make_fake_get(status_code=500))
    with pytest.raises(FetchError):
        get_data.fetch_xml()


def test_fetch_xml_network_error_raises_fetch_error(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", make_fake_get(exc=httpx.ConnectError("no route"))
    )
    with pytest.raises(FetchError):
        get_data.fetch_xml()


def test_fetch_xml_timeout_raises_fetch_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", make_fake_get(exc=httpx.TimeoutException("slow")))
    with pytest.raises(FetchError):
        get_data.fetch_xml()


def test_fetch_xml_uses_timeout(monkeypatch):
    captured = {}

    def spy_get(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, text=XML_SAMPLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", spy_get)
    get_data.fetch_xml()
    assert captured.get("timeout") is not None


# ---------------------------------------------------------------------------
# URL: задаётся в коде (константа), а не из окружения
# ---------------------------------------------------------------------------

def test_xml_url_default():
    assert get_data.xml_url() == "https://www.cbr-xml-daily.ru/daily_utf8.xml"


def test_fetch_xml_honors_explicit_url(monkeypatch):
    captured = {}

    def spy_get(url, **kwargs):
        captured["url"] = url
        return httpx.Response(200, text=XML_SAMPLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", spy_get)
    get_data.fetch_xml(url="https://mirror.example.com/feed.xml")
    assert captured["url"] == "https://mirror.example.com/feed.xml"


def test_list_rates_uses_explicit_url(monkeypatch):
    """URL передаётся из вызывающего кода (MCP-сервера), env не участвует."""
    captured = {}

    def spy_get(url, **kwargs):
        captured["url"] = url
        return httpx.Response(200, text=XML_SAMPLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", spy_get)
    get_data.list_rates(url="https://mirror.example.com/daily_utf8.xml")
    assert captured["url"] == "https://mirror.example.com/daily_utf8.xml"
    assert get_data.xml_url() == "https://www.cbr-xml-daily.ru/daily_utf8.xml"


# ---------------------------------------------------------------------------
# get_data / кеш
# ---------------------------------------------------------------------------

def test_get_data_downloads_parses_and_writes_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "get", make_fake_get())
    snap = _get_data()
    assert snap["date"] == XML_DATE
    assert len(snap["rates"]) == 4
    assert "timestamp" in snap

    cache_path = tmp_path / "cbr_rates_cache.json"
    assert cache_path.exists()
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert on_disk["date"] == XML_DATE
    assert on_disk["rates"][0]["code"] == "AUD"


def test_list_rates_downloads_when_no_cache(monkeypatch):
    monkeypatch.setattr(httpx, "get", make_fake_get())
    result = list_rates()
    assert result["date"] == XML_DATE
    assert len(result["rates"]) == 4


def test_list_rates_uses_fresh_cache_without_network(monkeypatch):
    seed_fresh_cache(monkeypatch)
    # сеть теперь запрещена — если list_rates полезет в неё, тест упадёт
    monkeypatch.setattr(httpx, "get", make_fake_get(exc=AssertionError("network!")))
    result = list_rates()
    assert result["date"] == XML_DATE
    assert len(result["rates"]) == 4


def test_list_rates_refreshes_stale_cache(monkeypatch, tmp_path):
    write_stale_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(httpx, "get", make_fake_get())
    result = list_rates()
    assert result["date"] == XML_DATE


def test_list_rates_http_error_is_error_not_empty(monkeypatch):
    monkeypatch.setattr(httpx, "get", make_fake_get(status_code=503))
    with pytest.raises(FetchError):
        list_rates()


# ---------------------------------------------------------------------------
# get_tickers / validate
# ---------------------------------------------------------------------------

def test_get_tickers_returns_pairs(monkeypatch):
    seed_fresh_cache(monkeypatch)
    pairs = get_tickers()
    assert ("USD", "Доллар США") in pairs
    assert ("JPY", "Иен") in pairs
    assert len(pairs) == 4


def test_validate_known_ticker(monkeypatch):
    seed_fresh_cache(monkeypatch)
    assert validate("AUD") is True


def test_validate_unknown_ticker(monkeypatch):
    seed_fresh_cache(monkeypatch)
    assert validate("XXX") is False


def test_validate_rub_base_currency(monkeypatch):
    """RUB — базовая валюта, её нет в XML, но она всегда доступна."""
    seed_fresh_cache(monkeypatch)
    assert validate("RUB") is True


def test_validate_case_insensitive(monkeypatch):
    seed_fresh_cache(monkeypatch)
    assert validate("aud") is True


# ---------------------------------------------------------------------------
# rate
# ---------------------------------------------------------------------------

def test_rate_per_unit_aud(monkeypatch):
    seed_fresh_cache(monkeypatch)
    result = rate("AUD", to_rub=False)
    assert result["code"] == "AUD"
    assert result["nominal"] == 1
    assert result["value"] == pytest.approx(57.7882)
    assert result["rate"] == pytest.approx(57.7882)
    assert result["date"] == XML_DATE


def test_rate_jpy_respects_nominal(monkeypatch):
    """JPY: 52.4668 руб. за 100 иен -> 0.524668 руб. за 1 иену."""
    seed_fresh_cache(monkeypatch)
    result = rate("JPY", to_rub=False)
    assert result["nominal"] == 100
    assert result["rate"] == pytest.approx(0.524668)


def test_rate_to_rub_inverts_currency(monkeypatch):
    """to_rub=True: сколько единиц валюты дают за 1 рубль."""
    seed_fresh_cache(monkeypatch)
    result = rate("AUD", to_rub=True)
    assert result["rate"] == pytest.approx(0.01730457082933886)


def test_rate_rub_base_returns_one(monkeypatch):
    seed_fresh_cache(monkeypatch)
    assert rate("RUB", to_rub=False)["rate"] == pytest.approx(1.0)
    assert rate("RUB", to_rub=True)["rate"] == pytest.approx(1.0)


def test_rate_unknown_raises(monkeypatch):
    seed_fresh_cache(monkeypatch)
    with pytest.raises(CurrencyNotFoundError):
        rate("XXX", to_rub=False)


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

def test_convert_usd_to_rub(monkeypatch):
    seed_fresh_cache(monkeypatch)
    result = convert(100, "USD", "RUB")
    assert result["from_amount"] == 100
    assert result["from_rate"] == pytest.approx(82.8504)
    assert result["to_rate"] == pytest.approx(1.0)
    assert result["to_amount"] == pytest.approx(8285.04)
    assert result["date"] == XML_DATE


def test_convert_jpy_to_rub_respects_nominal(monkeypatch):
    """1000 JPY = 1000 * (52.4668 / 100) = 524.668 RUB (номинал 100 учтён)."""
    seed_fresh_cache(monkeypatch)
    result = convert(1000, "JPY", "RUB")
    assert result["to_amount"] == pytest.approx(524.668)


def test_convert_rub_to_usd(monkeypatch):
    """100 RUB = 100 / 82.8504 = 1.21 USD (RUB — базовая валюта)."""
    seed_fresh_cache(monkeypatch)
    result = convert(100, "RUB", "USD")
    assert result["to_amount"] == pytest.approx(1.206994776126609)


def test_convert_cross_currency_usd_to_jpy(monkeypatch):
    """Кросс-курс без RUB: 100 USD = 100 * 82.8504 / (52.4668/100)."""
    seed_fresh_cache(monkeypatch)
    result = convert(100, "USD", "JPY")
    assert result["to_amount"] == pytest.approx(15791.01450822234)


def test_convert_same_currency(monkeypatch):
    seed_fresh_cache(monkeypatch)
    result = convert(50, "USD", "USD")
    assert result["to_amount"] == pytest.approx(50.0)


def test_convert_unknown_currency_raises(monkeypatch):
    seed_fresh_cache(monkeypatch)
    with pytest.raises(CurrencyNotFoundError):
        convert(100, "USD", "XXX")