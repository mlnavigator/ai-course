#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Извлечение ссылок из текста и их технических признаков.

Использование:
  python3 scripts/extract_links.py email.txt [--extra "url1 url2"]

Выход — JSON в stdout со списком ссылок и признаками.
Скрипт сообщает факты о ссылках, но не выносит вердикт о фишинге.
Ничего не скачивает и не открывает.
"""
import argparse
import ipaddress
import json
import re
import sys
from urllib.parse import urlsplit, unquote

URL_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}"
                    r"(?::\d+)?(?:/[^\s<>\"'()\[\]{}]*)?")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def analyze(raw):
    text = raw.strip()
    if not text.startswith(("http://", "https://", "www.")):
        text = "http://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    flags = []
    if parts.scheme == "https":
        flags.append("https")
    else:
        flags.append("http")
    port = parts.port
    if port not in (None, 80, 443):
        flags.append(f"нестандартный порт :{port}")
    if "@" in parts.netloc:
        flags.append("символ @ в адресе (маскировка реального хоста)")
    if "xn--" in host:
        flags.append("punycode в домене (международный домен)")
    try:
        ipaddress.ip_address(host)
        flags.append("хост — IP-адрес, а не доменное имя")
    except ValueError:
        pass
    if "%" in parts.path or "%" in parts.query:
        flags.append("percent-кодирование в пути/параметрах")
    if re.search(r"%[0-9a-fA-F]{2}", unquote(text)):
        flags.append("кодированные символы в ссылке")
    return {"url": raw, "scheme": parts.scheme, "host": host,
            "port": port, "path": parts.path[:120], "flags": flags}


def main(argv):
    parser = argparse.ArgumentParser(description="Извлечение ссылок")
    parser.add_argument("file", help="путь к тексту письма")
    parser.add_argument("--extra", default="", help="дополнительные ссылки через пробел")
    args = parser.parse_args(argv)

    try:
        with open(args.file, encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "links": [], "issues": [f"Не удалось прочитать файл: {exc}"]},
                         ensure_ascii=False))
        return 1

    raw_urls = URL_RE.findall(text)
    raw_urls += (args.extra or "").split()
    seen = set()
    links = []
    for raw in raw_urls:
        raw = raw.rstrip(".,;:)!]")
        if raw in seen:
            continue
        seen.add(raw)
        item = analyze(raw)
        if item is not None:
            links.append(item)

    links.sort(key=lambda item: item["url"])
    print(json.dumps({"ok": True, "count": len(links), "links": links}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))