# Примеры skills: готовые пакеты для агента

Здесь пять реальных, готовых к использованию навыков (skills) для ИИ-агента.
Каждый лежит в своей подпапке и устроен по правилам из `../skills_intro.md`:

- `SKILL.md` — YAML-заголовок (`name`, `description`) и инструкция;
- `scripts/` — Python-скрипты, которые выполняют точные вычисления;
- `references/` — справочники и правила, на которые ссылается инструкция;
- `assets/` — шаблоны выходных документов;
- `data/` — демо-материалы для проверки (в реальном пакете их может не быть).

Все скрипты используют только стандартную библиотеку Python, не ходят в сеть
и не изменяют входные файлы.

## Что входит

| Пакет | Что делает агент | Что делает скрипт | Демо-данные |
|---|---|---|---|
| `quiz-generator/` | Готовит опрос для самопроверки по тексту лекции | `check_answers.py` — проверяет ответы студента по опросу | Лекция про токены и контекст |
| `expense-report/` | Разбирает расходы за месяц и пишет отчёт | `aggregate_expenses.py` — считает суммы по категориям | CSV с расходами и дефектами |
| `meeting-notes/` | Превращает расшифровку встречи в протокол | `check_notes.py` — проверяет полноту протокола | Расшифровка планерки |
| `phishing-check/` | Анализирует подозрительное письмо по чек-листу | `extract_links.py` — извлекает ссылки и их признаки | Фишинговое письмо |
| `resume-review/` | Ревью резюме по чек-листу | `check_review.py` — проверяет, что все пункты чек-листа разобраны | Резюме студента |

## Как устроен один пакет

На примере `quiz-generator/`:

```
quiz-generator/
├── SKILL.md                     # инструкция для агента
├── scripts/
│   └── check_answers.py         # точная проверка ответов
├── assets/
│   └── quiz-template.md         # шаблон, по которому оформлять опрос
└── data/                        # демо-материалы (не обязательная часть пакета)
    ├── lecture-sample.md        #   текст лекции
    ├── questions-sample.json    #   опрос, как будто его собрал агент
    └── answers-sample.json      #   ответы студента
```

Папка пакета называется так же, как `name` в его YAML-заголовке.
Скрипты запускаются относительно корня пакета, например:

```bash
python3 scripts/check_answers.py data/questions-sample.json data/answers-sample.json
```

## Как пробовать

1. Запустите скрипт вручную на демо-данных — убедитесь, что он работает
   (ожидаемые результаты приведены в README каждого пакета).
2. Попросите агента применить пакет к демо-данным, например:
   «Разбери данные questions-sample.json и проверь ответы студента из
   answers-sample.json, используя skill quiz-generator».
3. Сравните вывод агента с результатом самостоятельного запуска скрипта.

## Как это связано с лекцией

- Описания пакетов видны агенту заранее, полная инструкция подгружается
  после выбора — *progressive disclosure*.
- Скрипт делает то, что должно вычисляться одинаково (проверка ответов,
  суммы, извлечение ссылок); содержание и вердикты — работа модели по правилам.
- Инструкции задают проверяемую процедуру: вход, порядок, правила, выход,
  проверку результата.
- Ни один пакет не выдаёт себя за «обученную нейросеть»: это файлы с
  инструкциями и кодом, которые интерпретирует агент.

## Как добавить свой skill

Скопируйте любой пакет, переименуйте папку и `name`, опишите свою задачу.
Минимальный пакет — один `SKILL.md`; скрипты, справочники и шаблоны
добавляйте только там, где они реально нужны.## Ожидаемые результаты проверочных запусков

Значения получены реальными запусками скриптов (Python 3, Linux, 2026-10-09).

### quiz-generator

```bash
cd 3_skils/examples/quiz-generator
python3 scripts/check_answers.py --validate data/questions-sample.json
# {"ok": true, "errors": []}

python3 scripts/check_answers.py data/questions-sample.json data/answers-sample.json
# ok=false, verdicts: {correct: 2, wrong: 1, unanswered: 1, manual: 2}
# issues: "В ответах есть ID, которых нет в опросе: Q7"
```

`manual` — открытые вопросы: их оценивает агент по эталону `expected`.

### expense-report

```bash
cd 3_skils/examples/expense-report
python3 scripts/aggregate_expenses.py data/expenses-sample.csv
```

Ожидаемо: `rows=9`, `excluded=3` (пустая категория, нечисловая сумма,
несуществующая дата), `total=26340.50`. Категории по убыванию: Жильё
18500.00, Развлечения 2500.00, Еда 2070.50, Транспорт 1520.00, Здоровье
1200.00, Связь 550.00.

### meeting-notes

```bash
cd 3_skils/examples/meeting-notes
python3 scripts/check_notes.py data/minutes-sample.json
# ok=true: 1 решение, 4 задачи, 2 открытых вопроса

python3 scripts/check_notes.py data/minutes-broken-sample.json
# ok=false: повтор id T-1, некорректная дата 2026-13-18,
# задача T-5 без дедлайна; warning: владелец «Егор» не в списке участников
```

### phishing-check

```bash
cd 3_skils/examples/phishing-check
python3 scripts/extract_links.py data/email-sample.txt
```

Ожидаемо: `count=2`. Главная ссылка `https://secure-bank-login.xyz/verify?user=confirm&code=%41%42`
с признаками `https`, `percent-кодирование`; отдельно зафиксирован голый домен.
Сверка с `references/red-flags.md` даёт: «срочно», «блокировка и заморозка»,
призыв ввести код — вердикт «подозрительно», переходить по ссылке нельзя.

### resume-review

```bash
cd 3_skils/examples/resume-review
python3 scripts/check_review.py references/checklist.md data/review-finished-sample.md
# ok=true: покрыты все K-01 … K-10
```

Если в отзыве пропустить пункт (например, K-06), скрипт сообщит
`missing: ["K-06"]` и ok=false.