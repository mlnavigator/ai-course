# SOLID на Python: пять принципов на одном примере

## 1. Что означают принципы

SOLID — ориентиры проектирования ответственности и зависимостей. Они не требуют интерфейса для каждого класса и не измеряются числом слоёв.

| Принцип | Вопрос к коду |
| --- | --- |
| SRP — Single Responsibility | Не смешаны ли причины изменения, относящиеся к разным обязанностям? |
| OCP — Open/Closed | Можно ли расширить реально изменяемую часть, не переписывая устойчивую логику? |
| LSP — Liskov Substitution | Сохраняет ли реализация поведенческий контракт при подстановке? |
| ISP — Interface Segregation | Не зависит ли клиент от операций, которые ему не нужны? |
| DIP — Dependency Inversion | Зависит ли правило от необходимого ему контракта, а не от технического механизма? |

Пример: система проверяет, можно ли выдать ещё один экземпляр. Есть число активных выдач, категория получателя и политика лимита. Этот пример только принимает решение; запись выдачи и конкурентное выполнение находятся вне его контракта.

## 2. Как выглядит проблема до разделения

Представьте одну функцию, которая выполняет SQL, выбирает лимит, проверяет задолженность, печатает JSON и отправляет email. Изменение формата ответа, схемы БД и правил выдачи затрагивает одно место.

Вместо запроса агенту «сделай SOLID» сначала назовите реальные причины изменений. В нашем случае отделим получение количества, политику лимита, принятие решения и представление результата.

## 3. Запускаемый пример

Python 3.11+, стандартная библиотека. Сохраните `solid_demo.py`, запустите `python solid_demo.py`. Ожидаются пять успешных тестов.

### Файл `solid_demo.py`

```python
from dataclasses import dataclass
from typing import Protocol
import json
import unittest


class ActiveLoanCounter(Protocol):
    # Контракт: возвращает неотрицательное целое число.
    def count_active(self, student_id: str) -> int: ...


class LimitPolicy(Protocol):
    # Категория задана приложением, не определяется самим счётчиком.
    # Для каждой поддерживаемой категории результат — целое > 0.
    def limit_for(self, category: str) -> int: ...


class InMemoryCounter:
    def __init__(self, counts: dict[str, int]):
        self._counts = dict(counts)

    def count_active(self, student_id: str) -> int:
        return self._counts.get(student_id, 0)


class StandardLimit:
    def limit_for(self, category: str) -> int:
        return 2


class CategoryLimit:
    def limit_for(self, category: str) -> int:
        return 4 if category == 'teacher' else 2


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


class CheckEligibility:
    def __init__(self, counter: ActiveLoanCounter, policy: LimitPolicy):
        self._counter = counter
        self._policy = policy

    def execute(self, student_id: str, category: str) -> Decision:
        if not student_id.strip():
            raise ValueError('Пустой ID')
        active = self._counter.count_active(student_id)
        limit = self._policy.limit_for(category)
        # Проверяем контракт зависимостей, включая bool как нежелательный int.
        if type(active) is not int or active < 0:
            raise ValueError('Нарушен контракт счётчика')
        if type(limit) is not int or limit <= 0:
            raise ValueError('Нарушен контракт политики')
        if active >= limit:
            return Decision(False, 'limit_reached')
        return Decision(True, 'allowed')


def render_json(decision: Decision) -> str:
    return json.dumps({'allowed': decision.allowed, 'reason': decision.reason})


class SolidTests(unittest.TestCase):
    def test_below_standard_limit(self):
        service = CheckEligibility(InMemoryCounter({'S-01': 1}), StandardLimit())
        self.assertEqual(service.execute('S-01', 'student'), Decision(True, 'allowed'))

    def test_at_standard_limit(self):
        service = CheckEligibility(InMemoryCounter({'S-01': 2}), StandardLimit())
        self.assertFalse(service.execute('S-01', 'student').allowed)

    def test_new_policy_changes_result_without_changing_service(self):
        counter = InMemoryCounter({'T-01': 3})
        self.assertFalse(CheckEligibility(counter, StandardLimit()).execute('T-01', 'teacher').allowed)
        self.assertTrue(CheckEligibility(counter, CategoryLimit()).execute('T-01', 'teacher').allowed)

    def test_broken_dependency_is_not_silently_accepted(self):
        class BrokenCounter:
            def count_active(self, student_id: str) -> int:
                return -1

        service = CheckEligibility(BrokenCounter(), StandardLimit())
        with self.assertRaisesRegex(ValueError, 'счётчика'):
            service.execute('S-01', 'student')

    def test_presentation_is_separate(self):
        result = json.loads(render_json(Decision(False, 'limit_reached')))
        self.assertEqual(result, {'allowed': False, 'reason': 'limit_reached'})


if __name__ == '__main__':
    unittest.main()
```

## 4. Разбор по принципам

### SRP

`InMemoryCounter` знает, откуда взять количество. Политика определяет лимит. `CheckEligibility` принимает решение, `render_json` представляет результат. Это разные причины изменения.

SRP не означает «в классе должен быть один метод». Несколько методов, обслуживающих одну согласованную ответственность, могут находиться вместе.

### OCP

Новая политика подключается аргументом конструктора. Менять `CheckEligibility` для категории преподавателя не понадобилось. Но место сборки приложения должно выбрать политику — OCP не запрещает любые правки вообще.

Если вариантов лимита нет и не ожидается реального изменения, простое число в конфигурации может быть лучше двух классов. Здесь варианты введены специально для демонстрации точки расширения.

### LSP

Счётчик, возвращающий `-1` или устаревший результат под видом достоверного, нарушает контракт независимо от правильной сигнатуры. В примере отрицательное значение обнаруживается явно. Достоверность числа требует проверки адаптера и условий его использования.

`StandardLimit` и `CategoryLimit` имеют разные бизнес-результаты, но обе выполняют объявленный общий контракт: положительный лимит. Конкретную выбранную политику всё равно надо сверять с требованиями. LSP не означает, что любая политика подходит любому заказчику.

### ISP

`CheckEligibility` нужны только `count_active` и `limit_for`. Не нужен общий интерфейс с операциями удаления студентов, печати актов и ремонта. Узкий контракт снижает объём ненужных зависимостей.

### DIP

Сценарий зависит от `ActiveLoanCounter`, а не от SQL-клиента. Конкретный объект передаётся снаружи. Это dependency injection обычным аргументом; отдельный контейнер не требуется.

`Protocol` описывает структурную типизацию: реализация не обязана наследоваться от него. Аннотации сами не запускают проверку типов и не доказывают поведенческий контракт. В примере часть контракта проверяется во время выполнения, часть — тестами.

## 5. Ограничение примера

Решение «можно выдать» может устареть до записи: два запроса увидят один свободный лимит. Если требование включает конкуренцию, проверка и изменение должны быть согласованы транзакционно. SOLID не создаёт эту гарантию.

## 6. Работа с ИИ

> Разбери причины изменения этого кода. Покажи конкретные нарушения контрактов и ненужные зависимости. Предложи минимальное разделение. Для каждой новой абстракции укажи, какую существующую потребность она обслуживает. Не создавай универсальные базовые классы.

Ревьюер проверяет подстановку реализаций и ошибки контрактов. Человек оценивает, оправдана ли цена абстракций. «Стало больше интерфейсов» не является критерием улучшения.

## 7. Самостоятельная работа

Добавьте запрет при текущей просрочке. Решите, нужен ли отдельный узкий интерфейс или имеющийся источник может вернуть осмысленный снимок состояния. Напишите тесты для отсутствия просрочки, просрочки при свободном лимите и сохранения прежних правил.

Затем реализуйте политику с лимитами из переданного словаря. Сценарий принятия решения менять нельзя. Определите поведение для неизвестной категории в спецификации, а не оставляйте его случайным.

## Источники

- [Robert C. Martin: Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html).
- [Python: typing.Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol).
