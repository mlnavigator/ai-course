# MVC на Python: модель, представление и контроллер

## 1. Зачем разделять роли

MVC — Model–View–Controller — разделяет модель, представление и обработку пользовательского ввода. Исторический MVC и варианты веб-фреймворков различаются. Здесь используется простой синхронный вариант для консольного интерфейса: контроллер разбирает команду, вызывает модель и передаёт результат представлению.

| Роль | Что делает в примере |
| --- | --- |
| Model | Хранит экземпляры и контролирует запрет повторной выдачи |
| View | Превращает данные и ожидаемые ошибки в текст |
| Controller | Разбирает ввод, выбирает операцию и организует вызовы |

Модель — не обязательно таблица БД. Контроллер — не место для всех бизнес-правил. Представление не должно менять состояние модели при выводе.

## 2. Запускаемый пример

Python 3.11+, стандартная библиотека. Сохраните `mvc_demo.py`. Тесты: `python mvc_demo.py`. Демонстрация команд: `python mvc_demo.py --demo`.

В коде фиксированный каталог, одна операция выдачи и просмотр списка. Возврат, история и хранение между запусками намеренно не реализованы.

### Файл `mvc_demo.py`

```python
from dataclasses import dataclass
import shlex
import sys
import unittest


class DomainError(ValueError):
    pass


@dataclass(frozen=True)
class ItemRow:
    number: str
    holder: str | None


class CatalogModel:
    def __init__(self, numbers: list[str]):
        self._holders: dict[str, str | None] = dict.fromkeys(numbers)

    def rows(self) -> tuple[ItemRow, ...]:
        return tuple(ItemRow(number, self._holders[number])
                     for number in sorted(self._holders))

    def issue(self, number: str, student_id: str) -> ItemRow:
        if number not in self._holders:
            raise DomainError('Экземпляр не найден')
        student_id = student_id.strip()
        if not student_id:
            raise DomainError('Пустой ID студента')
        if self._holders[number] is not None:
            raise DomainError('Экземпляр уже выдан')
        self._holders[number] = student_id
        return ItemRow(number, student_id)


class TextView:
    def listing(self, rows: tuple[ItemRow, ...]) -> str:
        return '\n'.join(f'{r.number}: {r.holder or "свободен"}' for r in rows)

    def issued(self, row: ItemRow) -> str:
        return f'Выдан {row.number} студенту {row.holder}'

    def error(self, message: str) -> str:
        return f'Ошибка: {message}'


class CatalogController:
    def __init__(self, model: CatalogModel, view: TextView):
        self._model = model
        self._view = view

    def handle(self, command: str) -> str:
        try:
            parts = shlex.split(command)
        except ValueError:
            return self._view.error('Некорректные кавычки')
        if parts == ['list']:
            return self._view.listing(self._model.rows())
        if len(parts) == 3 and parts[0] == 'issue':
            try:
                row = self._model.issue(parts[1], parts[2])
            except DomainError as exc:
                return self._view.error(str(exc))
            return self._view.issued(row)
        return self._view.error('Команды: list; issue <номер> <студент>')


class MvcTests(unittest.TestCase):
    def setUp(self):
        self.model = CatalogModel(['CAM-01', 'LAP-01'])
        self.controller = CatalogController(self.model, TextView())

    def test_model_checks_rules_without_controller(self):
        self.model.issue('CAM-01', 'S-01')
        with self.assertRaises(DomainError):
            self.model.issue('CAM-01', 'S-02')

    def test_controller_routes_command(self):
        self.assertEqual(self.controller.handle('issue CAM-01 S-01'),
                         'Выдан CAM-01 студенту S-01')
        self.assertIn('CAM-01: S-01', self.controller.handle('list'))

    def test_domain_error_is_presented(self):
        self.assertEqual(self.controller.handle('issue UNKNOWN S-01'),
                         'Ошибка: Экземпляр не найден')

    def test_bad_command_does_not_change_state(self):
        before = self.model.rows()
        self.assertTrue(self.controller.handle('issue CAM-01').startswith('Ошибка:'))
        self.assertEqual(self.model.rows(), before)

    def test_view_is_only_a_transformation(self):
        rows = (ItemRow('CAM-01', None),)
        self.assertEqual(TextView().listing(rows), 'CAM-01: свободен')
        self.assertIsNone(rows[0].holder)


if __name__ == '__main__':
    if sys.argv[1:] == ['--demo']:
        controller = CatalogController(CatalogModel(['CAM-01']), TextView())
        for command in ('list', 'issue CAM-01 S-01', 'issue CAM-01 S-02', 'list'):
            print('>', command)
            print(controller.handle(command))
    else:
        unittest.main()
```

Ожидается пять успешных тестов. В демонстрации сначала камера свободна, затем выдана S-01; повторная выдача S-02 отклоняется, S-01 остаётся владельцем.

## 3. Почему правило находится в модели

Если проверять занятость только в контроллере, другой вход — например, HTTP или импорт CSV — сможет обойти ограничение. Модель должна сохранять свои правила независимо от способа вызова.

Контроллер отвечает за синтаксис команды и выбор операции. Ошибка разбора кавычек — проблема входа, а занятость экземпляра — проблема предметной операции. Они обрабатываются на разных уровнях.

`TextView` получает неизменяемые строки данных и возвращает текст. Она не ходит в БД и не меняет модель. `print` находится в точке запуска; вместо него можно отправить полученный текст в другой интерфейс.

## 4. Как MVC сочетается с другими подходами

В более крупном приложении контроллер вызывает прикладной сценарий, который работает с доменной моделью и хранением. Тогда MVC организует вход и отображение, а Clean Architecture задаёт направления зависимостей всей системы.

В REST API без UI не обязательно выделять класс `View`. Сериализация ответа может быть обычной функцией. MVC не нужно воспроизводить буквально, если это добавляет пустой слой.

Наш пример не является полнофункциональным CLI: он не задаёт коды завершения на каждую доменную ошибку и не сохраняет данные. Его задача — показать роли. Добавляя настоящий CLI, определите и проверьте эти контракты отдельно.

## 5. Типичные ошибки

- Все проверки спрятаны в контроллере, модель разрешает недопустимые изменения.
- View выполняет SQL и изменяет состояние при отображении.
- Model означает только ORM-таблицу, а бизнес-правила разбросаны по обработчикам.
- Контроллер ловит любой `Exception` и превращает программный дефект в «неверную команду».
- Папки называются MVC, но код остаётся тесно связанным.

## 6. Задание агенту и ревью

> Добавь операцию возврата. Правило: вернуть можно только выданный экземпляр. Логику перехода размести в модели, разбор команды — в контроллере, текст — в представлении. Сначала добавь тесты. Не добавляй БД и веб-сервер.

Ревьюер проверяет вызов модели напрямую, не только через контроллер. Человек проверяет, осталось ли разделение простым и не появился ли лишний универсальный механизм команд.

## 7. Самостоятельная работа

1. Добавьте `return <номер>` и тесты возврата свободного и занятого экземпляра.
2. Напишите альтернативное JSON-представление с теми же операциями; доменную модель менять нельзя.
3. Убедитесь, что плохая команда не изменяет состояние.
4. Решите, должен ли пустой каталог отображаться пустой строкой или сообщением, и закрепите решение тестом.

## Источник

[Martin Fowler: Model View Controller](https://martinfowler.com/eaaCatalog/modelViewController.html). Консольный вариант и код — учебная иллюстрация разделения ролей.
