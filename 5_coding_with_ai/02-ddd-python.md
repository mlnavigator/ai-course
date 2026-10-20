# DDD на Python: модель предметной области

## 1. Что решает DDD

Domain-Driven Design помогает построить модель ПО вокруг понятий и правил предметной области. Начало работы — разговор о смысле, а не выбор ORM.

Заказчик говорит: «Студент берёт экземпляр оборудования и возвращает его. Один экземпляр нельзя выдать одновременно двум студентам. История должна сохраняться». Нам нужно различать физический экземпляр, запись о выдаче и состояние доступности.

DDD не требует микросервисов, большого числа классов или event sourcing. В маленьком приложении достаточно ясного языка и модели правил. В сложной системе дополнительно важны границы контекстов и взаимодействие разных моделей.

## 2. От языка к модели

| Понятие | Значение в примере | Представление |
| --- | --- | --- |
| Инвентарный номер | Идентификатор физического экземпляра | Объект-значение `InventoryNumber` |
| Экземпляр | Конкретная камера или ноутбук | Корень агрегата `Equipment` |
| Выдача | Факт передачи экземпляра студенту | Сущность `Loan` с ID |
| Активная выдача | Выдача без даты возврата | Вычисляемое состояние |
| Свободен | Нет активной выдачи | Производный признак |

**Сущность** сохраняет идентичность при изменении состояния. **Объект-значение** сравнивается по содержимому. **Агрегат** задаёт границу, внутри которой изменения проходят через корень и сохраняют локальные инварианты.

В этой учебной модели экземпляр управляет своей историей выдач. Это позволяет проверить «не более одной активной выдачи» внутри одного объекта. Цена: история растёт. Для большого объёма данных её хранение и границы загрузки пришлось бы пересмотреть.

## 3. Запускаемый пример

Python 3.11+, без внешних зависимостей. Сохраните файл и запустите `python ddd_demo.py`. В нём модель и пять проверок; БД и CLI специально отсутствуют.

### Файл `ddd_demo.py`

```python
from dataclasses import dataclass, replace
from datetime import date
from uuid import uuid4
import unittest


class DomainError(ValueError):
    pass


@dataclass(frozen=True)
class InventoryNumber:
    value: str

    def __post_init__(self):
        value = self.value.strip()
        if not value:
            raise DomainError('Пустой инвентарный номер')
        object.__setattr__(self, 'value', value)


@dataclass(frozen=True, eq=False)
class Loan:
    id: str
    student_id: str
    issued_on: date
    due_on: date
    returned_on: date | None = None

    def __post_init__(self):
        if not self.id.strip() or not self.student_id.strip():
            raise DomainError('ID не должен быть пустым')
        if self.due_on < self.issued_on:
            raise DomainError('Срок раньше выдачи')
        if self.returned_on is not None and self.returned_on < self.issued_on:
            raise DomainError('Возврат раньше выдачи')

    def __eq__(self, other):
        if not isinstance(other, Loan):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


class Equipment:
    def __init__(self, number: InventoryNumber):
        self.number = number
        self._loans: list[Loan] = []

    @property
    def history(self) -> tuple[Loan, ...]:
        return tuple(self._loans)

    @property
    def active_loan(self) -> Loan | None:
        return next((x for x in self._loans if x.returned_on is None), None)

    def issue(self, student_id: str, issued_on: date, due_on: date) -> Loan:
        if self.active_loan is not None:
            raise DomainError('Экземпляр уже выдан')
        loan = Loan(str(uuid4()), student_id.strip(), issued_on, due_on)
        self._loans.append(loan)
        return loan

    def return_loan(self, loan_id: str, returned_on: date) -> Loan:
        for index, loan in enumerate(self._loans):
            if loan.id != loan_id:
                continue
            if loan.returned_on is not None:
                raise DomainError('Выдача уже закрыта')
            closed = replace(loan, returned_on=returned_on)
            self._loans[index] = closed
            return closed
        raise DomainError('Выдача не найдена')


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.item = Equipment(InventoryNumber('CAM-01'))
        self.start = date(2030, 4, 10)
        self.due = date(2030, 4, 12)

    def test_value_object_normalizes_and_compares_by_value(self):
        self.assertEqual(InventoryNumber(' CAM-01 '), InventoryNumber('CAM-01'))
        with self.assertRaises(DomainError):
            InventoryNumber('   ')

    def test_second_issue_is_rejected_without_changing_history(self):
        first = self.item.issue('S-01', self.start, self.due)
        with self.assertRaises(DomainError):
            self.item.issue('S-02', self.start, self.due)
        self.assertEqual(self.item.history, (first,))

    def test_return_preserves_identity_and_allows_new_issue(self):
        first = self.item.issue('S-01', self.start, self.due)
        closed = self.item.return_loan(first.id, self.due)
        second = self.item.issue('S-02', self.due, self.due)
        self.assertEqual(first, closed)  # Одна идентичность, разное состояние.
        self.assertIsNone(first.returned_on)  # Старый снимок не изменился.
        self.assertEqual(closed.returned_on, self.due)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.item.history), 2)

    def test_invalid_return_preserves_active_loan(self):
        first = self.item.issue('S-01', self.start, self.due)
        with self.assertRaises(DomainError):
            self.item.return_loan(first.id, date(2030, 4, 9))
        self.assertIsNone(self.item.active_loan.returned_on)

    def test_repeat_return_is_rejected(self):
        first = self.item.issue('S-01', self.start, self.due)
        self.item.return_loan(first.id, self.due)
        with self.assertRaises(DomainError):
            self.item.return_loan(first.id, date(2030, 4, 13))
        self.assertEqual(self.item.history[0].returned_on, self.due)


if __name__ == '__main__':
    unittest.main()
```

## 4. Что здесь важно

`InventoryNumber(' CAM-01 ')` и `InventoryNumber('CAM-01')` равны по значению. У `Loan` сравнение намеренно основано на ID: две версии одной выдачи представляют одну сущность, хотя их даты возврата различаются. Поэтому в тестах состояния нужно проверять соответствующие поля, а не только равенство сущностей.

`Loan` сделан неизменяемым снимком. Корень создаёт новую версию при возврате. `history` возвращает кортеж, чтобы клиент случайно не дописал запись в список. Подчёркивание в `_loans` — соглашение Python, не механизм безопасности против намеренного вмешательства.

Методы предметной модели выражают операции `issue` и `return_loan`. Это полезнее публичного переключения `status = 'free'`: операция проверяет правила и меняет связанные данные.

## 5. Где заканчиваются гарантии агрегата

Объект предотвращает две активные выдачи внутри своего состояния. Два процесса могут загрузить разные копии и оба выполнить `issue`. Реальное хранилище должно обеспечивать согласованность транзакцией, ограничениями или контролем версии. Код примера не решает распределённую конкуренцию.

Лимит «не больше двух выдач на студента» охватывает несколько экземпляров. Его нельзя обеспечить, глядя только на один `Equipment`. Нужны запрос к общему состоянию и подходящая граница транзакции либо другая модель. Не складывайте всю систему в один гигантский агрегат только ради удобства.

## 6. Bounded context — граница смысла

В контексте выдач «доступен» означает возможность выдать экземпляр. В контексте ремонта «исправен» означает техническое состояние. Эти понятия связаны, но не идентичны: исправная камера может находиться у студента.

Для маленького приложения обе области можно оставить модулями одного контекста. Отдельный bounded context обосновывается самостоятельной моделью и языком, а не наличием новой таблицы. Сетевое разделение не обязательно.

## 7. Применение с ИИ

> По постановке выдели термины и инварианты. Для каждого правила покажи, какие данные нужны для проверки и кто ими владеет. Предложи минимальную модель и укажи правила, которые выходят за её локальную границу. Не начинай с SQL-таблиц и микросервисов.

Ревьюеру поручите попытаться нарушить правила через публичные операции и проверить сохранение истории при отказе. Человек проверяет смысл модели: действительно ли экземпляр и выдача обозначают разные вещи и подходит ли выбранная граница ответственности.

## 8. Самостоятельная работа

Добавьте обслуживание: только свободный экземпляр можно отправить на обслуживание; выдача на обслуживании запрещена; завершение возвращает доступность. Напишите таблицу переходов до кода, затем тесты. Обоснуйте, как хранится состояние и какие комбинации запрещены.

После этого спроектируйте, но пока не реализуйте лимит выдач на студента. Назовите данные и транзакционные гарантии, которых не хватает текущему агрегату.

## Источники

- [Eric Evans / Domain Language: DDD Reference](https://www.domainlanguage.com/ddd/reference/).
- [Python: dataclasses](https://docs.python.org/3/library/dataclasses.html).

Данная модель — один учебный вариант, а не универсальная структура для любого сервиса выдачи.
