# Clean Architecture на Python: зависимости направлены к правилам

## 1. Основная идея

Clean Architecture отделяет бизнес-правила от интерфейсов и технических механизмов. Внутренняя логика не импортирует внешний SQL-адаптер или веб-фреймворк. Внешние части знают контракт внутренней части и реализуют его.

Это правило зависимостей исходного кода, а не запрет сценарию вызвать БД во время выполнения. Сценарий вызывает переданный объект через контракт; создание конкретного объекта происходит снаружи.

| Модуль примера | Обязанность | Что импортирует из проекта |
| --- | --- | --- |
| `domain.py` | Экземпляр и правило выдачи | Ничего |
| `application.py` | Сценарий и контракт хранения | `domain` |
| `adapters.py` | Память и SQLite | `domain` |
| `main.py` | Сборка и запуск | `application`, `adapters` |
| `test_clean.py` | Проверка сценария с разными адаптерами | Вышеперечисленные модули |

В структурной типизации адаптеру необязательно импортировать `Protocol`, чтобы ему соответствовать. Зависимость от внутреннего контракта при этом остаётся смысловой: реализация должна соблюдать его.

## 2. Пример из пяти файлов

Создайте отдельную папку, сохраните в неё файлы ниже. Python 3.11+, без внешних зависимостей. Команды выполняются из этой папки:

```bash
python -m unittest -v test_clean
python main.py
```

### Файл `domain.py`

```python
from dataclasses import dataclass, replace


class DomainError(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    number: str
    holder: str | None = None

    def issue_to(self, student_id: str) -> 'Item':
        student_id = student_id.strip()
        if not student_id:
            raise DomainError('Пустой ID студента')
        if self.holder is not None:
            raise DomainError('Экземпляр занят')
        return replace(self, holder=student_id)
```

### Файл `application.py`

```python
from typing import Protocol
from domain import Item


class ItemRepository(Protocol):
    def get(self, number: str) -> Item | None: ...
    def save(self, item: Item) -> None: ...


class IssueItem:
    def __init__(self, repository: ItemRepository):
        self._repository = repository

    def execute(self, number: str, student_id: str) -> Item:
        item = self._repository.get(number)
        if item is None:
            raise LookupError('Экземпляр не найден')
        issued = item.issue_to(student_id)
        self._repository.save(issued)
        return issued
```

Контракт репозитория: `get` возвращает снимок или `None`; `save` сохраняет переданный снимок по номеру, создавая запись при отсутствии. `Item` неизменяем, поэтому изменение возвращённого экземпляра не может незаметно поменять хранилище без `save`.

### Файл `adapters.py`

```python
import sqlite3
from domain import Item


class MemoryItems:
    def __init__(self):
        self._items: dict[str, Item] = {}

    def get(self, number: str) -> Item | None:
        return self._items.get(number)

    def save(self, item: Item) -> None:
        self._items[item.number] = item


class SqliteItems:
    # Учебный адаптер владеет своим соединением и commit каждой save.
    def __init__(self, path: str):
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(
                'CREATE TABLE IF NOT EXISTS items '
                '(number TEXT PRIMARY KEY, holder TEXT)'
            )

    def get(self, number: str) -> Item | None:
        row = self._db.execute(
            'SELECT number, holder FROM items WHERE number = ?', (number,)
        ).fetchone()
        return Item(*row) if row is not None else None

    def save(self, item: Item) -> None:
        with self._db:
            self._db.execute(
                'INSERT INTO items(number, holder) VALUES (?, ?) '
                'ON CONFLICT(number) DO UPDATE SET holder = excluded.holder',
                (item.number, item.holder),
            )

    def close(self) -> None:
        self._db.close()
```

### Файл `main.py`

```python
from adapters import MemoryItems
from application import IssueItem
from domain import Item


def main():
    repository = MemoryItems()
    repository.save(Item('CAM-01'))
    result = IssueItem(repository).execute('CAM-01', 'S-01')
    print(f'{result.number}: выдан {result.holder}')


if __name__ == '__main__':
    main()
```

### Файл `test_clean.py`

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from adapters import MemoryItems, SqliteItems
from application import IssueItem
from domain import DomainError, Item


class CleanTests(unittest.TestCase):
    def test_same_use_case_with_two_adapters(self):
        for factory in (MemoryItems, lambda: SqliteItems(':memory:')):
            repository = factory()
            try:
                with self.subTest(adapter=type(repository).__name__):
                    repository.save(Item('CAM-01'))
                    service = IssueItem(repository)
                    self.assertEqual(service.execute('CAM-01', 'S-01').holder, 'S-01')
                    with self.assertRaises(DomainError):
                        service.execute('CAM-01', 'S-02')
                    self.assertEqual(repository.get('CAM-01').holder, 'S-01')
                    with self.assertRaises(LookupError):
                        service.execute('UNKNOWN', 'S-01')
            finally:
                if isinstance(repository, SqliteItems):
                    repository.close()

    def test_sqlite_survives_reopening(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / 'items.sqlite')
            first = SqliteItems(path)
            try:
                first.save(Item('CAM-01'))
                IssueItem(first).execute('CAM-01', 'S-01')
            finally:
                first.close()
            second = SqliteItems(path)
            try:
                self.assertEqual(second.get('CAM-01'), Item('CAM-01', 'S-01'))
            finally:
                second.close()

    def test_domain_rule_needs_no_repository(self):
        self.assertEqual(Item('CAM-01').issue_to('S-01').holder, 'S-01')
        with self.assertRaises(DomainError):
            Item('CAM-01').issue_to('   ')


if __name__ == '__main__':
    unittest.main()
```

Ожидаются три успешных тестовых метода; первый проверяет два адаптера через subtests. `main.py` выводит `CAM-01: выдан S-01`.

## 3. Где находится инверсия зависимости

`IssueItem` не создаёт `SqliteItems`. Он получает объект, у которого есть требуемые операции. В точке сборки можно выбрать память или SQLite без изменения сценария.

Вызов во время выполнения идёт из сценария к конкретному адаптеру. Импорты исходного кода внутреннего сценария не идут в модуль адаптеров. Это и позволяет тестировать сценарий отдельно от конкретной БД.

Передача зависимости через конструктор достаточна. DI-контейнер не является условием Clean Architecture.

## 4. Чего эта архитектура не гарантирует

**Пример рассчитан на последовательную работу.** Между `get` и `save` другой процесс может изменить запись. Два процесса способны успешно выдать одну камеру, а последняя запись затрёт первую. Отдельный commit внутри `save` не делает весь сценарий атомарным.

Для конкурентного варианта нужно изменить контракт: например, включить проверку версии и условное сохранение либо предоставить транзакционную границу вокруг чтения и изменения. Если операция меняет несколько записей, может понадобиться Unit of Work — объект, управляющий общей транзакцией сценария. Не добавляйте его без понимания необходимых гарантий.

Модель также не хранит историю выдач и не проверяет лимит студента. Эти возможности требуют собственных правил и тестов. Архитектурная схема не заменяет доменную модель.

## 5. Как не превратить подход в бюрократию

Не нужно создавать отдельный DTO и mapper для каждой функции. В примере наружу возвращается простой неизменяемый доменный объект: для такого масштаба это осознанное упрощение. В публичном API лучше определить отдельный контракт представления, если внутреннее устройство не должно становиться внешним обещанием.

Для небольшого скрипта выделение пяти файлов может быть избыточным. Здесь оно нужно, чтобы увидеть реальные импорты и зависимости, а не лишь названия классов в одном модуле.

## 6. Работа с агентами

> Добавь новый адаптер хранения, сохранив контракт репозитория. Внутренние модули не должны импортировать адаптер. Выполни общий набор проверок для старой и новой реализации. Отдельно укажи транзакционные гарантии и ограничения.

Ревьюер проверяет импорты, совпадение контрактов и отсутствие дублирования правил в адаптере. Человек решает, нужны ли эти границы и достаточно ли гарантий для реальной нагрузки.

## 7. Самостоятельная работа

1. Добавьте возврат экземпляра через новый прикладной сценарий и доменную операцию.
2. Проверьте возврат для памяти и SQLite, включая повторное открытие БД.
3. Добавьте автоматическую проверку запрета импорта `adapters` из `domain` и `application`.
4. Для усложнения реализуйте защиту от потерянного обновления с версией записи. Сначала определите конфликт и ожидаемую ошибку, затем тестируйте два независимых соединения.

## Источники

- [Robert C. Martin: The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html).
- [SQLite: Transactions](https://www.sqlite.org/lang_transaction.html).
- [Python: sqlite3](https://docs.python.org/3/library/sqlite3.html).
