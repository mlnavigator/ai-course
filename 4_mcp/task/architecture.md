источник данных https://www.cbr-xml-daily.ru/daily_utf8.xml

mcp сервер по stdio

метод 

### Реализуйте три tools

Новый файл `student_external.py`, сервер `cbr-rates`, результаты — словари для JSON.

| Tool | Аргументы | Результат |
|---|---|---|
| `list_rates` | — | `{"date": ..., "rates": [...]}`: код, номинал, имя, курс каждого `Valute` |
| `rate` | `code: str` | код, номинал, имя, курс, дата; неизвестный код — ошибка |
| `convert` | `amount: number`, `from_code: str`, `to_code: str` | `from_amount`, `from_rate`, `to_rate`, `to_amount`, `date`, где `to_amount = amount × (from_rate / from_nominal) / (to_rate / to_nominal)` |


 mcp_curses.py - mcp server
 с инструментами
 list_rates
 rate
 convert
 tickers - отдает список доступных тикеров
 сервер по stdio


 
 get_data.py
 
 get_data()
 - скачать и распарсить xml со страницы https://www.cbr-xml-daily.ru/daily_utf8.xml
 - сложить результат в json
 - в метаданные json указать timestamp скачивания
- актуальный список доступных курсов из поля <CharCode>BOB</CharCode>
 
 list_rates()
 - если json свежее 30 минут - то берем данные с него
 - если json более старый, то обновляем его
 - отдаем json вида `{"date": ..., "rates": [...]}`: код, номинал, имя, курс каждого `Valute`
 
validate(tiker: str) -> bool
- проверяет по списку доступных тикеров - есть ли он дост

rate(ticker: str, to_rub: bool)
- отдае курс за 1 руб. если to_rub=True, отдает курс за 1 единицу валюты если to_rub: False
 - принимает на вход тикер из <CharCode>BOB</CharCode>
 
 get_tickers() -> List[Tuple[str, str]]<Valute ID="R01135">
(HUF, Форинтов)
 отдает список пар - тикер и его название
 
convert(amount: int, tiker1: str, ticker2: str)
- переводит количество amount из валюты с ticker1 в валюту с ticker2


tests.py - тесты на модуль get_data по TDD

 

 
