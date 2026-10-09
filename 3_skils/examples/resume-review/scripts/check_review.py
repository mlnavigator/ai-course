#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка полноты отзыва о резюме относительно чек-листа.

Использование:
  python3 scripts/check_review.py references/checklist.md review.md

Чек-лист — markdown-список, пункты с кодами вида K-01.
Отзыв должен содержать те же коды (по одному разу).
Выход — JSON: ok, покрытые пункты, пропущенные, чужие коды.
"""
import json
import re
import sys

CODE_RE = re.compile(r"\bK-\d{2}\b")


def extract_codes(path, label):
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, UnicodeError) as exc:
        return None, [f"Не удалось прочитать {label}: {exc}"]
    codes = set(CODE_RE.findall(text))
    return codes, []


def main(argv):
    if len(argv) != 2:
        print(json.dumps({"ok": False,
                          "errors": ["Использование: python check_review.py checklist.md review.md"]},
                         ensure_ascii=False))
        return 2

    checklist_codes, errors_a = extract_codes(argv[0], "чек-лист")
    review_codes, errors_b = extract_codes(argv[1], "отзыв")
    if errors_a or errors_b:
        print(json.dumps({"ok": False, "errors": errors_a + errors_b}, ensure_ascii=False))
        return 1

    missing = sorted(checklist_codes - review_codes)
    extra = sorted(review_codes - checklist_codes)
    covered = sorted(checklist_codes & review_codes)

    result = {
        "ok": not missing and not extra,
        "total_in_checklist": len(checklist_codes),
        "covered": covered,
        "missing": missing,
        "extra_codes_in_review": extra,
        "errors": [],
    }
    if missing:
        result["errors"].append("В отзыве не разобраны пункты: " + ", ".join(missing))
    if extra:
        result["errors"].append("В отзыве есть коды, которых нет в чек-листе"
                                " (вероятно, опечатка): " + ", ".join(extra))

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))