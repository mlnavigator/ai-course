# Папка `example` — стартовый комплект по MCP

Учебные материалы раздела «MCP» курса — на них ссылаются методички `mcp_intro.md` и `mcp_practicum.md` (там это папка `example`). Внутри: готовые примеры MCP-серверов, клиент, учебная база данных, мок-API доставки и две заготовки для практикума.

## Что здесь лежит

| Файл | Что это | Как запустить |
|---|---|---|
| `requirements.txt` | Зафиксированные версии зависимостей: `mcp`, `fastapi`, `uvicorn`, `httpx` | `python -m pip install -r requirements.txt` |
| `client.py` | Универсальный MCP-клиент (CLI): показывает список tools или вызывает один tool | `python client.py SERVER.py` или `python client.py SERVER.py TOOL '{"арг": 1}'`; вместо пути можно передать HTTP URL сервера |
| `example_basic.py` | Минимальный MCP-сервер `price-demo` с одним tool `calculate_total` (расчёт стоимости покупки) | запускается автоматически клиентом: `python client.py example_basic.py calculate_total '{"price_kopecks":15000,"quantity":3}'` |
| `init_db.py` | Генератор учебной БД: создаёт схему и наполняет `shop.db` тестовыми данными | `python init_db.py` (повторно — только с `--reset`) |
| `shop.db` | SQLite-база магазина: таблицы `customers`, `products`, `orders`, `order_items` (4 клиента, 4 товара, 7 заказов, 9 позиций) | создана `init_db.py`, лежит готовая в комплекте |
| `example_sqlite.py` | MCP-сервер `sqlite-example`: tool `get_customer` читает клиента из SQLite (подключение read-only) | `python client.py example_sqlite.py get_customer '{"customer_id":1}'` |
| `mock_api.py` | Готовый HTTP API службы доставки (FastAPI, данные в памяти): `/health`, `/shipments`, `/shipping/quote`, перенос даты доставки | `python -m uvicorn mock_api:app --host 127.0.0.1 --port 8000`; документация на `http://127.0.0.1:8000/docs` |
| `example_http.py` | MCP-сервер `delivery-health-example`: tool `delivery_health` обращается к `/health` мок-API по HTTP (через `httpx`) | при запущенном мок-API: `python client.py example_http.py delivery_health` |
| `student_sqlite.py` | Заготовка для практикума: реализовать 4 tools (`find_products`, `get_order`, `customer_orders`, `sales_summary`) — SQL пишется здесь | наполняется студентом, затем `python client.py student_sqlite.py ...` |
| `student_api.py` | Заготовка для практикума: реализовать 4 tools (`list_deliveries`, `get_delivery`, `quote_delivery`, `reschedule_delivery`), обращаться к API только по HTTP | наполняется студентом, затем `python client.py student_api.py ...` |

## Как это связано с теорией

Три готовых сервера показывают три способа дать агенту инструменты:

1. **`example_basic.py`** — вычисление без внешних ресурсов (чистый код).
2. **`example_sqlite.py`** — доступ к локальной базе данных (SQLite).
3. **`example_http.py`** — доступ к внешнему сервису по HTTP (мок-API доставки).

`mock_api.py` — это обычный HTTP-сервис (не MCP): его оборачивают в MCP-сервер. `student_*.py` — задания практикума на ту же тему: обернуть БД и HTTP API.

## Быстрый старт (Bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 1) минимальный сервер: показать tools и вызвать tool
python client.py example_basic.py
python client.py example_basic.py calculate_total '{"price_kopecks":15000,"quantity":3}'

# 2) сервер над SQLite
python client.py example_sqlite.py get_customer '{"customer_id":1}'

# 3) сервер, вызывающий HTTP-API (в отдельном терминале запущен mock_api.py)
python -m uvicorn mock_api:app --host 127.0.0.1 --port 8000
# во втором терминале:
python client.py example_http.py delivery_health
```

Клиент сам запускает и завершает MCP-процесс — отдельно запускать `example_basic.py`/`example_sqlite.py`/`example_http.py` не нужно.

## Как использовать в практикуме

1. **Правятся только два файла:** `student_sqlite.py` и `student_api.py` — в каждом реализуются 4 tools (списки в таблице выше). Имена tools и сигнатуры менять нельзя: на них завязаны проверки практикума и `client.py`. Остальные файлы — готовые, их не редактируют.
2. **CLI-клиент для проверки:**
   ```bash
   python3 client.py student_sqlite.py                 # список tools; пока пустой — функции не зарегистрированы
   python3 client.py student_sqlite.py get_order '{"order_id":101}'
   python3 client.py student_api.py quote_delivery '{"weight_grams":1500,"zone":"local"}'
   ```
   В командах методичек используется `python`; если он не найден, заменяйте на `python3`.
3. **Примеры — образцы подхода, а не решения:** tools в `example_basic.py` (`calculate_total`), `example_sqlite.py` (`get_customer`) и `example_http.py` (`delivery_health`) не входят в задание. Они показывают стиль (read-only SQLite, `httpx` + таймаут, обработка ошибок), но требуемые восемь tools студенты пишут сами.

## Примечания

- **Восстановление базы:** `python init_db.py --reset` (сбрасывает только учебную `shop.db`).
- **Транспорт HTTP:** чтобы запустить MCP-сервер не через stdio, скопируйте `example_basic.py` в `example_basic_http.py` и замените последнюю строку на `mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)`, затем подключайтесь клиентом по URL: `python client.py http://127.0.0.1:8001/mcp ...`.
- **Адрес мок-API** задаётся переменной окружения `DELIVERY_API_URL` (по умолчанию `http://127.0.0.1:8000`); адрес БД — `SHOP_DB` (по умолчанию `shop.db` рядом со скриптом).
- **Готовых решений** `student_sqlite.py` и `student_api.py` в комплекте нет — их пишут студенты.
- Windows: команды из методички `mcp_intro.md` (активация `.venv`, кавычки для JSON в PowerShell).