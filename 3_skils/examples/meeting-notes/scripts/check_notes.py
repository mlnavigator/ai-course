#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка протокола встречи (minutes.json) на полноту и согласованность.

Использование:
  python3 scripts/check_notes.py minutes.json [minutes2.json ...]

Выход — JSON: errors (обязательные проблемы) и warnings (обратить внимание).
Код завершения 0, если ошибок нет.
"""
import datetime
import json
import sys


def check_unique_ids(items, kind, errors, warnings):
    seen = {}
    for item in items or []:
        if not isinstance(item, dict):
            errors.append(f"{kind}: элемент не является объектом")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{kind}: элемент без id")
            continue
        if item_id in seen:
            errors.append(f"{kind}: повтор id={item_id}")
        seen[item_id] = item
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            errors.append(f"{kind} {item_id}: пустой текст")


def parse_date(raw, label, errors):
    if not raw or not isinstance(raw, str):
        errors.append(f"{label}: отсутствует или не строка")
        return None
    try:
        return datetime.date.fromisoformat(raw.strip())
    except ValueError:
        errors.append(f"{label}: некорректная дата {raw!r}, нужен формат YYYY-MM-DD")
        return None


def check_minutes(data):
    errors = []
    warnings = []

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["Протокол не является объектом JSON"], "warnings": []}

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("Нет названия встречи (title)")

    meeting_date = parse_date(data.get("date"), "date встречи", errors)

    participants = data.get("participants")
    if not isinstance(participants, list) or not participants:
        errors.append("Список участников пуст или отсутствует")
        participants = []
    else:
        bad = [p for p in participants if not isinstance(p, str) or not p.strip()]
        if bad:
            errors.append("В списке участников есть пустые элементы")

    decisions = data.get("decisions", [])
    tasks = data.get("tasks", [])
    questions = data.get("open_questions", [])
    for name, items in (("decisions", decisions), ("tasks", tasks),
                        ("open_questions", questions)):
        if not isinstance(items, list):
            errors.append(f"{name}: должен быть списком")
            continue
        check_unique_ids(items, name, errors, warnings)

    participant_set = {p.strip() for p in participants if isinstance(p, str)}
    owners = set()
    for task in tasks or []:
        item_id = task.get("id") if isinstance(task, dict) else "?"
        owner = (task.get("owner") or "").strip() if isinstance(task, dict) else ""
        if not owner:
            errors.append(f"Задача {item_id}: нет владельца (owner)")
            continue
        owners.add(owner)
        if participant_set and owner not in participant_set:
            warnings.append(
                f"Задача {item_id}: владелец {owner!r} не в списке участников — "
                "добавьте его в participants или подтвердите присутствие")
        deadline = parse_date(task.get("deadline"), f"дедлайн задачи {item_id}", errors)
        if deadline is not None and meeting_date is not None and deadline < meeting_date:
            warnings.append(f"Задача {item_id}: дедлайн {deadline} раньше даты встречи {meeting_date}")

    if participant_set and owners:
        idle = sorted(participant_set - owners)
        if idle:
            warnings.append("Участники без назначенных задач: " + ", ".join(idle) +
                            " (возможно, просто присутствовали)")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def main(argv):
    if not argv:
        print(json.dumps({"ok": False, "files": [],
                          "errors": ["Использование: python check_notes.py minutes.json [minutes2.json ...]"]},
                         ensure_ascii=False))
        return 2

    files = []
    any_errors = False
    for path in argv:
        try:
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            files.append({"path": path, "ok": False,
                          "errors": [f"Не удалось прочитать файл: {exc}"], "warnings": []})
            any_errors = True
            continue
        result = check_minutes(data)
        any_errors = any_errors or not result["ok"]
        files.append({"path": path, **result,
                      "summary": {"decisions": len(data.get("decisions", [])),
                                  "tasks": len(data.get("tasks", [])),
                                  "open_questions": len(data.get("open_questions", [])),
                                  "participants": len(data.get("participants", []))}})

    print(json.dumps({"ok": not any_errors, "files": files}, ensure_ascii=False))
    return 0 if not any_errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))