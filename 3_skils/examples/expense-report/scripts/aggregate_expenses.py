#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Агрегация расходов из CSV по категориям.

Использование:
  python3 scripts/aggregate_expenses.py data/expenses.csv [--currency ₽]

Выход — JSON в stdout: общий итог, суммы по категориям, по дням, проблемы.
Строки с ошибками исключаются из сумм и перечисляются в issues.
Входной файл не изменяется.
"""
import argparse
import csv
import datetime
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

REQUIRED = {"date", "category", "amount"}


def parse_amount(raw):
    if raw is None:
        return None
    text = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    text = text.rstrip("рР.")
    if not text:
        return None
    text = text.replace(",", ".")
    if text.count(".") > 1:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(raw):
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def aggregate(path, currency):
    issues = []
    rows = []
    try:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = [f.strip() for f in (reader.fieldnames or [])]
            missing = sorted(REQUIRED - set(fields))
            if missing:
                return {"ok": False,
                        "errors": ["Отсутствуют колонки: " + ", ".join(missing)],
                        "rows": 0, "total": "0.00", "categories": [],
                        "by_date": [], "issues": []}
            for index, row in enumerate(reader, start=2):
                problems = []
                d = parse_date(row.get("date"))
                if d is None:
                    problems.append("некорректная дата")
                cat = (row.get("category") or "").strip()
                if not cat:
                    problems.append("пустая категория")
                else:
                    if "," in cat or "\t" in cat:
                        problems.append("категория содержит разделитель")
                        cat = None
                amt = parse_amount(row.get("amount"))
                if amt is None:
                    problems.append("некорректная сумма")
                if problems:
                    issues.append({"row": index, "problems": problems,
                                   "note": (row.get("note") or "")[:80]})
                    continue
                rows.append({"date": str(d), "category": cat, "amount": amt})
    except (OSError, UnicodeError, csv.Error) as exc:
        return {"ok": False, "errors": [f"Не удалось прочитать CSV: {exc}"],
                "rows": 0, "total": "0.00", "categories": [], "by_date": [],
                "issues": []}

    total = sum((r["amount"] for r in rows), Decimal("0.00")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r["amount"])
    categories = sorted(
        ({
            "category": cat,
            "total": str(sum(vals, Decimal("0.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "count": len(vals),
        } for cat, vals in by_cat.items()),
        key=lambda item: Decimal(item["total"]), reverse=True)

    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r["amount"])
    by_date = sorted(
        ({
            "date": day,
            "total": str(sum(vals, Decimal("0.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "count": len(vals),
        } for day, vals in by_day.items()),
        key=lambda item: item["date"])

    return {
        "ok": True,
        "currency": currency,
        "rows": len(rows),
        "excluded": len(issues),
        "total": str(total),
        "categories": categories,
        "by_date": by_date,
        "issues": issues,
    }


def main(argv):
    parser = argparse.ArgumentParser(description="Агрегация расходов")
    parser.add_argument("csv", help="путь к CSV с расходами")
    parser.add_argument("--currency", default="₽", help="символ валюты")
    args = parser.parse_args(argv)
    result = aggregate(args.csv, args.currency)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))