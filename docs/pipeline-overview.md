# CI Pipeline Overview

## Назначение

Workflow `Security CI` встроен в процесс разработки FastAPI-приложения. Он запускает базовые engineering-проверки и security-проверки автоматически, чтобы ошибки, небезопасный код, секреты и уязвимые зависимости выявлялись до merge в основную ветку.

Это практический пример принципа **shift left**: проверки выполняются максимально рано, на этапе разработки и code review.

---

## Когда запускается pipeline

Workflow расположен в файле:

```text
.github/workflows/security-ci.yml
```

Он запускается:

- при `push` в любую ветку;
- при создании или обновлении Pull Request, направленного в ветку `main`.

---

## Последовательность этапов

```text
push / pull request
        |
        v
Checkout repository
        |
        v
Set up Python and install dependencies
        |
        v
Run pytest
        |
        v
Run Bandit SAST scan
        |
        v
Run Gitleaks secret scan
        |
        v
Run pip-audit dependency scan
        |
        v
Build Docker image
        |
        v
Upload security reports artifact
```

Все основные проверки выполняются в одном job:

```text
Tests, security scans and Docker build
```

Такой подход выбран для первой версии проекта, чтобы этапы были понятны и выполнялись в строгой последовательности.

---

## Описание шагов

| Шаг | Назначение |
|---|---|
| Check out repository | Загружает исходный код в GitHub Actions runner |
| Set up Python | Устанавливает Python и использует pip cache |
| Install dependencies | Устанавливает зависимости приложения и инструменты разработки |
| Create reports directory | Создаёт каталог для JSON-отчётов security-инструментов |
| Run application tests | Запускает автоматические тесты pytest |
| Run Bandit SAST scan | Анализирует Python-код на потенциально опасные паттерны |
| Install Gitleaks | Устанавливает инструмент поиска секретов |
| Run Gitleaks secret scan | Проверяет рабочие файлы и Git-историю на секреты |
| Run pip-audit dependency scan | Проверяет зависимости на известные vulnerabilities |
| Build Docker image | Проверяет, что Docker image приложения успешно собирается |
| Upload security reports | Сохраняет отчёты как GitHub Actions artifact |

---

## Почему Gitleaks проверяет Git-историю

В workflow используется настройка:

```yaml
fetch-depth: 0
```

Она загружает полную Git-историю, а не только последний commit.

Это важно, потому что секрет может быть удалён из текущей версии файла, но остаться доступным в более раннем commit. Gitleaks должен иметь возможность обнаружить такой случай.

---

## Отчёты как artifacts

В процессе CI создаются JSON-отчёты:

```text
reports/bandit-report.json
reports/gitleaks-report.json
reports/pip-audit-report.json
```

Они загружаются в GitHub Actions под именем:

```text
security-reports
```

Для загрузки используется условие:

```yaml
if: always()
```

Это означает, что GitHub Actions всё равно попытается сохранить доступные отчёты, даже если одна из предыдущих проверок завершилась ошибкой.

Отчёты не коммитятся в Git-репозиторий: каталог `reports/` исключён через `.gitignore`. Так репозиторий не засоряется результатами отдельных запусков CI.

---

## Политика результата

Pipeline считается успешным, если:

- все pytest-тесты прошли;
- Bandit не вернул блокирующих находок;
- Gitleaks не нашёл потенциальных секретов;
- `pip-audit` не нашёл известных уязвимостей согласно политике проекта;
- Docker image успешно собрался.

Если любой обязательный этап завершается с ошибкой, job становится красным. Изменение должно быть исправлено либо пройти ручной security-триаж до merge.
