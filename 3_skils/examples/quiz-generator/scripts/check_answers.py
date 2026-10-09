#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка ответов студента и валидация файла опроса.

Использование:
  python3 scripts/check_answers.py questions.json answers.json
  python3 scripts/check_answers.py --validate questions.json

Выход — JSON в stdout, в нём же причины проблем.
Код завершения 0, если проверка прошла без структурных ошибок.
"""
import json
import sys


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def validate_quiz(questions):
    """Возвращает (errors, by_id). Проверяет структуру опроса."""
    errors = []
    by_id = {}
    for index, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            errors.append(f"Вопрос {index}: элемент не является объектом")
            continue
        qid = q.get("id")
        if not isinstance(qid, str) or not qid.strip():
            errors.append(f"Вопрос {index}: нет id")
            continue
        if qid in by_id:
            errors.append(f"Повтор id={qid}")
            continue
        qtype = q.get("type")
        if qtype not in ("choice", "open"):
            errors.append(f"Вопрос {qid}: неизвестный тип {qtype!r}, должно быть choice или open")
            continue
        if not isinstance(q.get("text"), str) or not q["text"].strip():
            errors.append(f"Вопрос {qid}: пустой текст вопроса")
        if qtype == "choice":
            options = q.get("options")
            if not isinstance(options, list) or not (2 <= len(options) <= 6):
                errors.append(f"Вопрос {qid}: нужно от 2 до 6 вариантов")
            else:
                if len(set(options)) != len(options):
                    errors.append(f"Вопрос {qid}: повторяющиеся варианты")
                answer_index = q.get("answer_index")
                if not isinstance(answer_index, int) or not (0 <= answer_index < len(options)):
                    errors.append(
                        f"Вопрос {qid}: answer_index должен быть от 0 до {len(options)-1}"
                    )
        else:
            if not isinstance(q.get("reference"), str) or not q["reference"].strip():
                errors.append(f"Вопрос {qid}: нет эталонного ответа reference")
        by_id[qid] = q
    return errors, by_id


def grade(questions, by_id, answers):
    answer_map = {}
    for item in answers.get("answers", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            answer_map[item["id"]] = item

    per_question = []
    verdicts = {"correct": 0, "wrong": 0, "unanswered": 0, "manual": 0}
    issues = []

    for qid, q in by_id.items():
        entry = {"id": qid, "type": q.get("type"), "topic": q.get("topic"),
                 "text": q.get("text"), "verdict": None}
        student = answer_map.get(qid)
        if student is None:
            entry["verdict"] = "unanswered"
            verdicts["unanswered"] += 1
            per_question.append(entry)
            continue

        if q["type"] == "choice":
            options = q["options"]
            chosen = student.get("choice")
            if not isinstance(chosen, int) or not (0 <= chosen < len(options)):
                entry["verdict"] = "invalid"
                issues.append(f"Вопрос {qid}: номер варианта вне диапазона 0..{len(options)-1}")
            else:
                entry["chosen"] = options[chosen]
                if chosen == q.get("answer_index"):
                    entry["verdict"] = "correct"
                    verdicts["correct"] += 1
                else:
                    entry["verdict"] = "wrong"
                    entry["expected"] = options[q["answer_index"]]
                    verdicts["wrong"] += 1
        else:
            text = student.get("text")
            if not isinstance(text, str) or not text.strip():
                entry["verdict"] = "unanswered"
                verdicts["unanswered"] += 1
            else:
                entry["verdict"] = "manual"
                entry["student"] = text
                entry["expected"] = q.get("reference")
                verdicts["manual"] += 1
        per_question.append(entry)

    unknown = sorted(qid for qid in answer_map if qid not in by_id)
    if unknown:
        issues.append("В ответах есть ID, которых нет в опросе: " + ", ".join(unknown))

    return {
        "ok": not issues,
        "title": questions.get("title", ""),
        "total": len(by_id),
        "verdicts": verdicts,
        "questions": per_question,
        "issues": issues,
    }


def main(argv):
    if len(argv) == 2 and argv[0] == "--validate":
        try:
            questions = read_json(argv[1])
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "errors": [f"Не удалось прочитать опрос: {exc}"]},
                             ensure_ascii=False))
            return 1
        items = questions.get("questions")
        if not isinstance(items, list) or not items:
            print(json.dumps({"ok": False, "errors": ["В файле опроса нет списка questions"]},
                             ensure_ascii=False))
            return 1
        errors, _ = validate_quiz(items)
        print(json.dumps({"ok": not errors, "title": questions.get("title", ""),
                          "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0

    if len(argv) != 2:
        print(json.dumps({"ok": False,
                          "errors": ["Использование: python check_answers.py questions.json answers.json "
                                     "или python check_answers.py --validate questions.json"]},
                         ensure_ascii=False))
        return 2

    try:
        questions = read_json(argv[0])
        answers = read_json(argv[1])
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"Не удалось прочитать файл: {exc}"]},
                         ensure_ascii=False))
        return 1

    if not isinstance(answers, dict):
        print(json.dumps({"ok": False, "errors": ["Файл ответов должен быть объектом с полем answers"]},
                         ensure_ascii=False))
        return 1

    items = questions.get("questions")
    if not isinstance(items, list) or not items:
        print(json.dumps({"ok": False, "errors": ["В файле опроса нет списка questions"]},
                         ensure_ascii=False))
        return 1

    errors, by_id = validate_quiz(items)
    if errors:
        print(json.dumps({"ok": False, "errors": ["Опрос не прошёл валидацию", *errors]},
                         ensure_ascii=False))
        return 1

    result = grade(questions, by_id, answers)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))