# Каталог skills для AI-агентов: где брать и что ставить

Проверено 09.10.2026. Все ссылки и репозитории ниже проверены по первоисточнику:
звёзды и даты последнего коммита взяты из GitHub API, у ключевых пакетов прочитан
реальный `SKILL.md` (файл с YAML-заголовком `name` + `description` + инструкцией) —
это то, что и делает пакет «скиллом», а не пустышкой. Сомнительные и
недоступные каталоги (skillsmp.com, claudeskills.info и т.п.) в доку **не включены**.

Формат «skills» (папка с `SKILL.md` + опционально `scripts/`, `references/`,
`assets/`, `data/`) поддерживают Claude Code, Cursor, Windsurf, GitHub Copilot,
Gemini CLI, OpenAI Codex и ещё ~20 инструментов. Общий стандарт — [agentskills.io](https://agentskills.io).

---

## 1. Официальные и эталонные

### anthropics/skills — официальный репозиторий Anthropic
- **Ссылка:** https://github.com/anthropics/skills
- **Что это:** эталонный набор скиллов от разработчиков Claude. Здесь видно,
  как правильно устроены скиллы: структура папки, YAML-заголовок, инструкция,
  references. Сюда же выложена **спецификация формата** (`spec/`) и **шаблон**
  (`template/`) для создания своих скиллов.
- **Что внутри (19 скиллов):**
  - Документы: `docx`, `pdf`, `pptx`, `xlsx` — создание и редактирование Word,
    PDF, PowerPoint, Excel (это те же скиллы, что крутят встроенные документные
    возможности Claude);
  - Дизайн и креатив: `canvas-design`, `frontend-design`, `algorithmic-art`,
    `theme-factory`, `web-artifacts-builder`, `slack-gif-creator`;
  - Разработка и техника: `mcp-builder` (сборка MCP-серверов), `webapp-testing`,
    `claude-api`, `skill-creator` (создание и улучшение самих скиллов);
  - Корпоративное: `brand-guidelines` (брендбук компании), `doc-coauthoring`,
    `internal-comms`, `academy-guide`, `discernment-nudge`.
- **Для чего нужен:** изучать по нему, как писать качественные скиллы, и брать
  готовые документные скиллы. Установка в Claude Code одной командой
  `/plugin marketplace add anthropics/skills` (пакеты `document-skills` и
  `example-skills`).
- **Проверка:** ~180 000 звёзд; последний коммит — в день проверки; в
  `skills/skill-creator/SKILL.md` прочитан реальный YAML-заголовок (name/description).

### spec и документы стандарта
- **agentskills.io** — описание стандарта Agent Skills (формат `SKILL.md`,
  метаданные, как скилл загружается агентом).
- **Документация Claude Code про skills:** https://code.claude.com/docs/en/skills —
  как включить, создать, распространять скиллы.
- **Статья «Equipping agents for the real world with Agent Skills»:**
  https://anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills —
  как устроен механизм скиллов изнутри, от инженеров Anthropic.

---

## 2. Каталоги и подборки (где искать скиллы)

### ComposioHQ/awesome-claude-skills — большая курируемая подборка
- **Ссылка:** https://github.com/ComposioHQ/awesome-claude-skills
- **Что это:** классический awesome-список: скиллы, ресурсы и инструменты для
  кастомизации Claude, разложенные по категориям (документы, тестирование,
  безопасность, медиа, данные, DevOps, frontend, backend, research и т.д.).
- **Для чего нужен:** быстрый обзор экосистемы и переход по ссылкам на
  конкретные скиллы от сообщества.
- **Проверка:** ~77 000 звёзд, обновляется (последний коммит 18.09.2026).

### travisvn/awesome-claude-skills — ещё одна курируемая подборка
- **Ссылка:** https://github.com/travisvn/awesome-claude-skills
- **Что это:** аналогичный curated-список, с фокусом на Claude Code, включая
  FAQ (например, как монетизировать скиллы, где искать).
- **Для чего нужен:** перекрёстная проверка находок из другой подборки, раздел
  вопросов и ответов.
- **Проверка:** ~15 000 звёзд, обновлён 28.04.2026.

### heilcheng/awesome-agent-skills + npx skills — каталог и менеджер
- **Ссылка:** https://github.com/heilcheng/awesome-agent-skills
- **Сайт-каталог:** https://www.agent-skill.co
- **Что это:** каталог скиллов с категориями (документы, презентации, таблицы…)
  плюс CLI-инструмент `npx skills`: `skills find <запрос>`,
  `skills add owner/repo`, `skills list`, `skills check`, `skills update`.
- **Для чего нужен:** искать скиллы из терминала и ставить одной командой;
  `skills check` проверяет корректность установленного скилла.
- **Проверка:** ~6 300 звёзд, обновлён 05.04.2026; каталог-сайт открывается и
  содержит разбивку по категориям.

### skills.sh — лидерборд и директория скиллов (от Vercel)
- **Ссылка:** https://www.skills.sh
- **Что это:** каталог с поиском и «лидербордом»: показывает топ репозиториев
  со скиллами, число установок и активности каждого пакета. Репозиторий
  инструмента: https://github.com/vercel-labs/skills (CLI `npx skills`).
- **Для чего нужен:** быстрый взгляд на то, какие скиллы реально популярны и
  обновляются.
- **Проверка:** сайт открывается, лидерборд показывает живые пакеты
  (mattpocock/skills, microsoft/azure-skills, google/agents-cli, prisma/skills и др.)
  с числом установок.

---

## 3. Методологические пакеты (как агент пишет и проверяет код)

### obra/superpowers — фреймворк разработки для агента
- **Ссылка:** https://github.com/obra/superpowers
- **Что это:** «скиллы-надстройка» над агентом: методология разработки
  (планирование → написание кода → тесты → ревью → завершение ветки).
  15 скиллов: `writing-plans`, `executing-plans`, `test-driven-development`,
  `systematic-debugging`, `brainstorming`, `requesting-code-review`,
  `receiving-code-review`, `subagent-driven-development`,
  `using-git-worktrees`, `verification-before-completion`, `writing-skills`,
  `dispatching-parallel-agents`, `finishing-a-development-branch` и др.
- **Для чего нужен:** превратить агента из «пишет код наугад» в агента,
  который сначала составляет план, пишет тесты и проверяет результат.
  Одна из самых известных методологий в экосистеме.
- **Проверка:** ~297 000 звёзд, коммиты в день проверки; прочитан реальный
  `skills/writing-plans/SKILL.md` (name/description на месте).

### mattpocock/skills — скиллы практикующего инженера
- **Ссылка:** https://github.com/mattpocock/skills
- **Что это:** набор скиллов Мэтта Покока (известный автор курсов по TypeScript)
  «из его собственной `.agents`-папки» — проверенные в реальной работе инженера.
- **Что внутри:** категория `engineering` — `code-review`, `diagnosing-bugs`,
  `codebase-design`, `domain-modeling`, `implement`, `implement-spec`, `tdd`,
  `prototype`, `triage`, `pr`, `research`, `retro`, `wayfinder`, `wizard`;
  категория `productivity` — `grill-me`, `grilling`, `teach`, `handoff`,
  `to-questionnaire`, `writing-for-agents`, `wait-what`;
  категория `misc` — `git-guardrails-claude-code`, `setup-pre-commit` и др.
- **Для чего нужен:** готовые рабочие процессы «как инженер»: ревью, поиск багов,
  ретроспектива, обучение агента — вместо того чтобы изобретать свои.
- **Проверка:** ~282 000 звёзд, коммиты в день проверки; прочитан
  `skills/engineering/code-review/SKILL.md`.

---

## 4. Вендорские пакеты (облако и инструменты)

### microsoft/azure-skills — официальный пакет Microsoft для Azure
- **Ссылка:** https://github.com/microsoft/azure-skills
- **Что это:** официальный плагин-агент: скиллы и конфигурации MCP-серверов
  для типовых сценариев Azure.
- **Что внутри (28 скиллов):** `azure-ai` (AI Search, Speech, OpenAI,
  Document Intelligence), `azure-deploy`, `azure-storage`, `azure-kubernetes`,
  `azure-compliance`, `azure-diagnostics`, `azure-reliability`,
  `azure-resource-visualizer`, `azure-cloud-migrate`, `azure-quotas`,
  `entra-app-registration`, `entra-agent-id`, `microsoft-foundry`,
  `appinsights-instrumentation`, `azure-messaging`, `azure-kusto` и др.
- **Для чего нужен:** если работаешь с Azure — агент получает проверенные
  инструкции по развёртыванию, диагностике, комплаенсу и ИИ-сервисам Azure,
  не выдумывая их.
- **Проверка:** ~1 600 звёзд, коммит в день проверки, официальная организация
  Microsoft; прочитан `skills/azure-ai/SKILL.md`.

### google/agents-cli — CLI и скиллы Google для AI-агентов
- **Ссылка:** https://github.com/google/agents-cli
- **Что это:** официальный CLI Google + 7 скиллов для создания, оценки и
  развёртывания AI-агентов на Google Cloud (фреймворк ADK).
- **Что внутри:** `google-agents-cli-adk-code` (написание кода агента),
  `google-agents-cli-deploy`, `google-agents-cli-eval`, `google-agents-cli-observability`,
  `google-agents-cli-publish`, `google-agents-cli-scaffold`, `google-agents-cli-workflow`.
- **Для чего нужен:** разработка агентов на Google Cloud руками Claude/Gemini —
  каркас, код, оценка, деплой, наблюдаемость.
- **Проверка:** ~6 000 звёзд, коммит 06.10.2026, официальная организация
  Google; прочитан `skills/google-agents-cli-adk-code/SKILL.md`.

---

## 5. Узкоспециализированные и исследовательские

### llllllama/RigorPilot-Skills — скиллы для воспроизводимых исследований
- **Ссылка:** https://github.com/lllllllama/RigorPilot-Skills
- **Что это:** скиллы «README-first» для воспроизведения научных результатов:
  ограниченное исполнение, проверяемые следы (auditable evidence) и аннотации
  поверх README, которые не портят исходный файл.
- **Для чего нужен:** если агент должен воспроизводить эксперименты/статьи и
  оставлять проверяемый след, а не «верить на слово».
- **Проверка:** ~500 звёзд, обновлён 23.09.2026, реальные скиллы в репозитории.

### alirezarezvani/claude-skills — большая коллекция скиллов и плагинов
- **Ссылка:** https://github.com/alirezarezvani/claude-skills
- **Что это:** коллекция на ~380 скиллов, 30+ агентов и 70+ кастомных команд
  для Claude Code/Codex/Gemini. Автор активно публикует обзоры на Medium.
- **Для чего нужен:** «каталог на любой вкус»: от бэкенда до медиа; годится,
  чтобы быстро найти скилл под конкретную задачу.
- **Проверка:** ~28 000 звёзд, обновлён 30.08.2026. Учесть: коллекция большая,
  качество отдельных скиллов перед установкой стоит проверять
  (`npx skills check` или чтение SKILL.md).

---

## 6. Полезные материалы на русском

- **«Skills для Claude Code: огромный гайд от инженера Anthropic» (Хабр):**
  https://habr.com/ru/articles/1011524/ — перевод/адаптация урока изнутри
  Anthropic: какие типы скиллов существуют, как написать хороший скилл,
  когда делиться. Проверено: статья открывается, содержит разбор категорий.
- **«Где искать скиллы для Claude Code в 2026» (EdgeLab Space):**
  https://blog.edgelab.space/guides/gde-iskat-skilly-claude-code/ — русскоязычный
  обзор 8 репозиториев (включая anthropics/skills и ComposioHQ) с метриками.
- **Наши примеры:** `3_skils/examples/README.md` — 5 учебных скиллов на русском
  с проверяемыми скриптами (quiz-generator, expense-report, meeting-notes,
  phishing-check, resume-review).

---

## Как установить скилл (кратко)

1. Скилл — это папка с `SKILL.md`; положи её в `.claude/skills/` (Claude Code)
   или в соответствующую папку своего агента, либо подключи репозиторий как
   plugin-marketplace: `/plugin marketplace add anthropics/skills`.
2. Проверь пакет перед установкой: посмотри `SKILL.md` (есть ли `name` и
   `description`, понятная инструкция), загляни в `scripts/` — скрипты должны
   делать то, что заявлено, и не делать ничего лишнего.
3. `npx skills check` — проверит корректность установленных скиллов.

Числа звёзд и даты — на момент проверки (09.10.2026), для «лайф-чека»
популярности пакета заглядывай на GitHub.