# %% [markdown]
# # Блок 1. Ноутбук 5 — Структурированный вывод и tool calling
#
# Курс: «Современное использование ИИ в бизнесе и разработке ПО».
#
# В этом ноутбуке:
#
# - зачем нужен структурированный вывод (JSON, JSON mode, JSON Schema);
# - почему «валидный JSON» ≠ «правильный ответ»;
# - Pydantic как контракт приложения;
# - три уровня надёжности структурированного вывода;
# - tool calling: кто реально выполняет функцию и почему аргументам модели нельзя
#   верить безусловно;
# - безопасный цикл с registry, валидацией и аудитом.
#
# Материал соответствует разделам 15 и 16 конспекта лекции.

# %% [markdown]
# ## 1. Зачем нужен структурированный вывод
#
# Свободный текст удобен человеку, но неудобен программе. Production-система
# обычно ожидает данные фиксированной структуры:
#
# ```json
# {
#   "category": "technical",
#   "priority": "high",
#   "requires_human": false
# }
# ```

# %%
import json
from typing import Literal

# %% [markdown]
# ## 2. Три уровня надёжности
#
# ### Уровень 1 — «просто верни JSON»
#
# Модель может добавить Markdown-обёртку, пояснение или сломать синтаксис.
#
# ### Уровень 2 — JSON mode
#
# API ограничивает вывод синтаксически корректным JSON. Но поля и значения могут
# не соответствовать бизнес-схеме:
#
# ```json
# {"importance": "очень срочно", "topic": 17}
# ```
#
# JSON валиден, но непригоден.
#
# ### Уровень 3 — Structured Outputs / JSON Schema
#
# Задаётся схема типов, обязательных полей, enum и запрет лишних полей.
# Строгость зависит от модели и провайдера.

# %% [markdown]
# ## 3. JSON Schema для классификатора обращений
#
# Схема из конспекта (раздел 15.2, уровень 3):

# %%
ticket_schema = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["billing", "delivery", "technical", "cancellation"],
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "requires_human": {"type": "boolean"},
    },
    "required": ["category", "priority", "requires_human"],
    "additionalProperties": False,
}

print(json.dumps(ticket_schema, ensure_ascii=False, indent=2))

# %% [markdown]
# ## 4. Валидный JSON ≠ правильный ответ
#
# Схема гарантирует, что `priority` входит в enum, но **не** что модель верно
# оценила приоритет. Нужны: валидация структуры, доменные проверки, тестовые
# примеры и при необходимости human review.

# %%
# Пример: JSON валиден, но «приоритет» семантически сомнителен.
sample_output = {"category": "technical", "priority": "high", "requires_human": False}
print("Поля:", sorted(sample_output))
print("priority в enum:", sample_output["priority"] in ticket_schema["properties"]["priority"]["enum"])
# Вопрос к тебе: high обоснован? Схема это не проверит — решает доменный код/человек.

# %% [markdown]
# ## 5. Pydantic как контракт приложения
#
# Даже если API обещает схему, объект полезно проверять **на границе своего
# приложения** — Pydantic это удобно кодирует.

# %%
from pydantic import BaseModel, ValidationError

TICKET_CATEGORIES = Literal["billing", "delivery", "technical", "cancellation"]
TICKET_PRIORITIES = Literal["low", "medium", "high"]


class TicketClassification(BaseModel):
    category: TICKET_CATEGORIES
    priority: TICKET_PRIORITIES
    requires_human: bool


# Валидный объект
good = TicketClassification.model_validate(sample_output)
print("Валидный:", good)

# Невалидный — priority вне enum
bad = {"category": "technical", "priority": "urgent", "requires_human": False}
try:
    TicketClassification.model_validate(bad)
except ValidationError as exc:
    print("Отловлено отклонение:")
    print(exc)

# %% [markdown]
# ### 5.1. Обработка ошибок
#
# Структурированный вызов может завершиться не обычным объектом:
#
# - отказ модели по политике;
# - превышение лимита;
# - оборванный ответ;
# - несовместимость провайдера со схемой;
# - тайм-аут;
# - валидный объект с неверной семантикой.

# %%
def parse_ticket(raw: str | None) -> TicketClassification:
    """Разбирает сырой JSON в модель Pydantic, бросая понятные исключения."""
    if raw is None:
        raise RuntimeError("Пустой ответ модели")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Некорректный JSON") from exc
    try:
        return TicketClassification.model_validate(obj)
    except ValidationError as exc:
        raise RuntimeError("Невалидная схема") from exc


for raw in ['{"category":"billing","priority":"low","requires_human":false}',
            'не json',
            '{"category":"billing","priority":"lowest","requires_human":false}']:
    try:
        parsed = parse_ticket(raw)
        print(f"OK -> {parsed}")
    except RuntimeError as exc:
        print(f"Ошибка -> {exc}")

# %% [markdown]
# ## 6. Tool calling
#
# **Tool calling** — соглашение, при котором приложению передают описание
# доступных функций, а модель может вернуть структурированное предложение
# вызвать функцию.
#
# **Ключевой факт:**
#
# > Модель обычно не выполняет вашу Python-функцию. Она выбирает инструмент
# > и генерирует аргументы. Выполнение делает ваш код.

# %% [markdown]
# ### 6.1. Цикл вызова
#
# 1. приложение отправляет сообщения и описание инструментов;
# 2. модель отвечает tool call: имя + JSON-аргументы;
# 3. приложение валидирует аргументы и права;
# 4. приложение выполняет функцию;
# 5. результат добавляется в диалог как tool result;
# 6. модель формирует пользовательский ответ или вызывает следующий инструмент.

# %% [markdown]
# ### 6.2. Описание инструмента
#
# Хорошее описание отвечает на вопросы: когда использовать, когда нет, что
# означают параметры, какие ограничения, есть ли побочные эффекты.

# %%
get_order_status_tool = {
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": "Возвращает текущий статус заказа по его ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "ID вида ORD-12345",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
}

print(json.dumps(get_order_status_tool, ensure_ascii=False, indent=2))

# %% [markdown]
# ## 7. Упрощённый цикл выполнения в коде
#
# Реализуем registry инструментов, валидацию аргументов и безопасное выполнение.
# В реальной системе добавляют авторизацию, idempotency-ключи, тайм-ауты и аудит.

# %%
import re

ORDER_ID_PATTERN = re.compile(r"^ORD-\d{5}$")

# Псевдобаза заказов (для демонстрации, не для продакшена).
ORDER_DB = {
    "ORD-00001": {"status": "delivered", "delivered": True},
    "ORD-00002": {"status": "in_delivery", "delivered": False},
}


def get_order_status(order_id: str) -> dict:
    """Чтение: вернуть статус заказа."""
    if order_id not in ORDER_DB:
        return {"order_id": order_id, "error": "order_not_found"}
    return {"order_id": order_id, **ORDER_DB[order_id]}


def cancel_order(order_id: str, reason: str, confirmed: bool) -> dict:
    """Изменение: отменить заказ (только при явном подтверждении и не для доставленных)."""
    if not confirmed:
        return {"order_id": order_id, "error": "confirmation_required"}
    if order_id not in ORDER_DB:
        return {"order_id": order_id, "error": "order_not_found"}
    if ORDER_DB[order_id]["delivered"]:
        return {"order_id": order_id, "error": "cannot_cancel_delivered"}
    return {"order_id": order_id, "status": "cancelled"}


TOOL_REGISTRY = {
    "get_order_status": get_order_status,
    "cancel_order": cancel_order,
}

TOOL_ARG_SCHEMAS = {
    "get_order_status": {"order_id": str},
    "cancel_order": {"order_id": str, "reason": str, "confirmed": bool},
}


def validate_arguments(name: str, arguments: dict) -> None:
    """Проверяет аргументы до вызова: типы и формат order_id."""
    schema = TOOL_ARG_SCHEMAS.get(name, {})
    for key, expected in schema.items():
        if key not in arguments:
            raise ValueError(f"Отсутствует аргумент '{key}' для '{name}'")
        if not isinstance(arguments[key], expected):
            raise TypeError(f"Аргумент '{key}' имеет неверный тип для '{name}'")
    oid = arguments.get("order_id")
    if oid is not None and not ORDER_ID_PATTERN.fullmatch(oid):
        raise ValueError(f"Некорректный order_id: {oid!r}")


def execute_tool_call(name: str, raw_arguments: str) -> dict:
    """Безопасное выполнение инструмента: валидация -> registry -> вызов."""
    if name not in TOOL_REGISTRY:
        raise RuntimeError(f"Неизвестный инструмент: {name}")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Аргументы не являются JSON") from exc

    # В прод пишут: schema-валидация, авторизация и аудит.
    validate_arguments(name, arguments)
    return TOOL_REGISTRY[name](**arguments)


# %% [markdown]
# ### 7.1. Демонстрация безопасного цикла
#
# Покажем: чтение работает, отмена без подтверждения отклоняется, отмена
# доставленного заказа запрещена, несуществующий инструмент отклоняется.

# %%
calls = [
    ("get_order_status", '{"order_id": "ORD-00002"}'),
    ("cancel_order", '{"order_id": "ORD-00002", "reason": "передумал", "confirmed": false}'),
    ("cancel_order", '{"order_id": "ORD-00001", "reason": "передумал", "confirmed": true}'),
    ("not_a_tool", '{}'),
]

for name, raw in calls:
    try:
        result = execute_tool_call(name, raw)
        print(f"{name:16} -> {result}")
    except Exception as exc:
        print(f"{name:16} -> ОШИБКА: {exc}")

# %% [markdown]
# ## 8. Почему аргументам модели нельзя доверять
#
# Модель может:
#
# - указать несуществующий ID;
# - передать лишние параметры;
# - попытаться выйти за допустимую директорию;
# - выбрать инструмент с опасным побочным эффектом;
# - неверно понять пользователя;
# - повторить один и тот же вызов.
#
# Поэтому нужны:
#
# - schema validation;
# - allowlist инструментов;
# - проверка полномочий пользователя;
# - idempotency-ключи;
# - тайм-ауты и лимиты;
# - подтверждение для необратимых действий;
# - журналирование;
# - нормализация результата инструмента.

# %% [markdown]
# ### 8.1. Чтение и действие — разные классы риска
#
# - `get_order_status` — чтение;
# - `cancel_order` — изменение состояния;
# - `refund_payment` — финансовое действие.
#
# Для действий с последствиями модель **не** должна быть единственным субъектом
# авторизации: инструмент проверяет права независимо от текста промпта.

# %% [markdown]
# ## 9. Structured output и tool calling — не одно и то же
#
# | Механизм | Назначение |
# |---|---|
# | Structured output | вернуть данные приложению в заданной форме |
# | Tool calling | попросить приложение выполнить внешнюю операцию |
#
# Если нужно классифицировать заявку — инструмент не нужен.
# Если нужно проверить статус в CRM — без инструмента у модели нет актуальных данных.

# %% [markdown]
# ## 10. Итоги ноутбука
#
# - JSON / JSON mode / JSON Schema — три уровня надёжности структурированного вывода.
# - Валидный JSON не означает правильный ответ; нужны доменные проверки.
# - Pydantic — удобный контракт на границе приложения.
# - Модель не выполняет инструменты — она предлагает вызов, а выполняет ваш код.
# - Аргументы и действия нужно валидировать и авторизовывать в коде, не в промпте.
#
# Дальше — контекст-инжиниринг и шаблонизация промптов (Jinja2).