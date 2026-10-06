# %% [markdown]
# # Блок 1. Ноутбук 7 — Практика: OpenAI-compatible API и OpenRouter
#
# Курс: «Современное использование ИИ в бизнесе и разработке ПО».
#
# В этом ноутбуке:
#
# - что означает «OpenAI-compatible» и чего это не гарантирует;
# - базовый вызов Chat Completions через OpenAI SDK;
# - надёжный минимальный wrapper с retry;
# - прямой HTTP-запрос (для диагностики несовместимости SDK);
# - OpenRouter как агрегатор моделей и сравнение моделей;
# - как проверять результат программно, а не «на глаз».
#
# Материал соответствует разделам 21 и 22 конспекта лекции.
#
# > **Важно про окружение.** Этот ноутбук делает сетевые запросы к API.
# > Ключи читаются из переменных окружения / файла `.env` (UTF-8) в папке
# > `lectures`. Если API недоступен, ячейки **безопасно пропускаются** с
# > пояснением — ноутбук выполняется сверху вниз без падений.

# %% [markdown]
# ## 1. Импорты и подготовка окружения
#
# Пробуем загрузить `.env` (если есть) и проверяем наличие API-ключей.

# %%
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Загружаем ключи из .env, если файл существует.
if load_dotenv is not None:
    load_dotenv(Path(".") / ".env", override=False)

API_KEY = os.environ.get("LLM_API_KEY", "").strip()
BASE_URL = os.environ.get("LLM_BASE_URL", "").strip() or "https://api.openai.com/v1"
MODEL = os.environ.get("LLM_MODEL", "").strip() or "default-model"

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODELS = [m.strip() for m in os.environ.get("OPENROUTER_MODELS", "").split(",") if m.strip()]

print("LLM_API_KEY задан:", bool(API_KEY))
print("LLM_BASE_URL:", BASE_URL)
print("LLM_MODEL:", MODEL or "(не задан)")
print("OPENROUTER_API_KEY задан:", bool(OPENROUTER_KEY))
print("OPENROUTER_MODELS:", OPENROUTER_MODELS or "(не заданы)")


def have_openai_api() -> bool:
    """Живой ли OpenAI-compatible конфиг."""
    return bool(API_KEY) and bool(MODEL) and BASE_URL != "https://api.openai.com/v1"


def have_openrouter() -> bool:
    return bool(OPENROUTER_KEY) and bool(OPENROUTER_MODELS)

# %% [markdown]
# ## 2. Что означает OpenAI-compatible
#
# Обычно провайдер реализует HTTP-интерфейс, похожий на OpenAI Chat Completions:
# endpoint `/chat/completions`, роли `system/user/assistant/tool`, поля
# `model`, `messages`, `temperature`, `tools`; можно использовать OpenAI SDK с
# другим `base_url`.
#
# **Compatible не означает идентичный.** Могут различаться:
#
# - доступные поля;
# - роли сообщений;
# - structured outputs;
# - tool calling;
# - reasoning-параметры;
# - подсчёт токенов;
# - streaming;
# - сообщения об ошибках;
# - значения `usage`;
# - семантика `stop` и max tokens.

# %% [markdown]
# ## 3. Базовый вызов Chat Completions (через SDK)
#
# Если ключей нет — ячейка напечатает инструкцию и завершится без ошибки.

# %%
if not have_openai_api():
    print("API не настроен. Скопируйте .env.example в .env и укажите")
    print("LLM_API_KEY / LLM_BASE_URL / LLM_MODEL. Ячейки с вызовами пропущены.")
else:
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Ты классификатор обращений. Следуй только заданной системе категорий.",
            },
            {
                "role": "user",
                "content": (
                    "Категории: billing, delivery, technical, cancellation.\n"
                    "Обращение: После обновления приложение не запускается.\n"
                    "Верни только категорию."
                ),
            },
        ],
        temperature=0,
    )

    print("Ответ модели:", response.choices[0].message.content)

# %% [markdown]
# ## 4. Надёжный минимальный wrapper
#
# Повтор допустим не всегда: автоматически повторять операцию с побочным
# эффектом без idempotency нельзя. Чтение (классификация) повторять можно.

# %%
if not have_openai_api():
    print("API не настроен — определение wrapper без вызова.")
else:
    import time
    from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30.0, max_retries=0)


    def call_llm(messages: list[dict], attempts: int = 3) -> str:
        for attempt in range(attempts):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=0,
                )
                content = response.choices[0].message.content
                if not content:
                    raise RuntimeError("Модель вернула пустой ответ")
                return content
            except (RateLimitError, APITimeoutError, APIConnectionError):
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError("Недостижимо")

    print("Определена функция call_llm с retry (3 попытки, экспоненциальная пауза).")

# %% [markdown]
# ## 5. Прямой HTTP-запрос
#
# Прямой HTTP полезен для понимания протокола и диагностики несовместимости SDK.

# %%
if not have_openai_api():
    print("API не настроен — прямой HTTP пропущен.")
else:
    import requests

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "Объясни KV-cache в трёх предложениях."}
        ],
        "temperature": 0.2,
    }

    response = requests.post(
        f"{BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    print(data["choices"][0]["message"]["content"])

# %% [markdown]
# ## 6. OpenRouter — агрегатор моделей
#
# OpenRouter даёт единый API для моделей разных поставщиков: сравнение моделей,
# быстрое переключение, прототипирование, fallback, единый биллинг.
#
# **Единый endpoint не устраняет различия моделей:** перед использованием нужно
# проверить, поддерживает ли конкретная модель tool calling, structured outputs,
# нужную длину контекста и параметры reasoning.

# %%
if not have_openrouter():
    print("OpenRouter не настроен. Укажите OPENROUTER_API_KEY и OPENROUTER_MODELS.")
else:
    from openai import OpenAI

    client = OpenAI(
        api_key=OPENROUTER_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODELS[0],
        messages=[
            {
                "role": "system",
                "content": "Отвечай как технический преподаватель, точно и кратко.",
            },
            {
                "role": "user",
                "content": "Чем context window отличается от max output tokens?",
            },
        ],
        temperature=0.2,
    )
    print(response.choices[0].message.content)
    print("usage:", response.usage)

# %% [markdown]
# ### 6.1. Сравнение двух моделей
#
# Это **демонстрация**, а не полноценный benchmark: один пример не позволяет
# ранжировать модели. Модели перечислены в `OPENROUTER_MODELS` через запятую.

# %%
if not have_openrouter():
    print("OpenRouter не настроен — сравнение пропущено.")
else:
    from openai import OpenAI

    client = OpenAI(
        api_key=OPENROUTER_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    prompt = """
Найди дефект в функции и предложи минимальное исправление:

def mean(values):
    return sum(values) / len(values)

Учитывай пустой список. Ответ: проблема, исправленный код, один тест.
    """.strip()

    for model in OPENROUTER_MODELS[:3]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            print(f"\n--- {model} ---")
            print(response.choices[0].message.content)
        except Exception as exc:
            print(f"\n--- {model} --- ОШИБКА: {exc}")

# %% [markdown]
# ### 6.2. Что проверять при смене модели
#
# - следует ли она формату;
# - корректно ли вызывает инструменты;
# - поддерживает ли схему;
# - не меняет ли язык ответа;
# - как ведёт себя при недостатке данных;
# - какова latency;
# - сколько токенов потребляет;
# - насколько стабилен результат;
# - каков фактический тариф;
# - какая политика хранения данных у маршрута.

# %% [markdown]
# ## 7. Проверка результата программно
#
# Полагаться только на «убедительность» текста нельзя. Минимальная проверка:
# убедиться, что ответ есть и попадает в ожидаемый набор.

# %%
EXPECTED_CATEGORIES = {"billing", "delivery", "technical", "cancellation"}


def validate_category(raw: str) -> str:
    """Проверяет, что ответ — ровно одна допустимая категория."""
    value = raw.strip().lower().strip("`\"' .")
    if value not in EXPECTED_CATEGORIES:
        raise ValueError(f"Недопустимая категория: {value!r}")
    return value


if have_openai_api():
    from openai import OpenAI
    import time
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    _client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30.0, max_retries=0)

    messages = [
        {"role": "system", "content": "Ты классификатор обращений. Верни только категорию."},
        {"role": "user", "content": "Как скачать чек за прошлый месяц? Категории: billing, delivery, technical, cancellation."},
    ]
    try:
        resp = _client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
        raw = resp.choices[0].message.content or ""
        cat = validate_category(raw)
        print("Сырой ответ:", raw)
        print("Проверенная категория:", cat)
    except Exception as exc:
        # Сетевая недоступность превращаем в мягкое предупреждение.
        print("Не удалось выполнить проверку (сеть/ключ):", type(exc).__name__, exc)
        print("Код проверки остаётся рабочим — запустите при настроенном API.")

# %% [markdown]
# ## 8. Итоги ноутбука
#
# - OpenAI-compatible — это близкий, но не идентичный интерфейс; различия надо
#   проверять на документации конкретного провайдера.
# - Надёжный вызов оборачивают в retry с экспоненциальной паузой (и не повторяют
#   операции с побочным эффектом без idempotency).
# - Прямой HTTP помогает диагностировать несовместимость SDK.
# - OpenRouter удобен для сравнения моделей, но смена модели — через eval-набор.
# - Результат проверяется программно (валидация формата/значений), а не «на глаз».
#
# На этом блок 1 завершён. Дальше — блок про эмбеддинги, векторные БД и RAG.