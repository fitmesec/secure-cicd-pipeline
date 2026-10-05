# Secure CI/CD Pipeline Overview

## Назначение

Workflow `Secure CI/CD` автоматизирует проверку, публикацию и развёртывание FastAPI-приложения.

Pipeline реализует принцип **shift left security**: тесты и security-проверки выполняются до публикации Docker image и deployment в staging-среду.

Workflow расположен в файле:

```text
.github/workflows/security-ci.yml
```

Он состоит из трёх последовательных job:

1. **Tests, security scans and Docker build** — CI-проверки;
2. **Publish Docker image to GHCR** — сборка и публикация versioned Docker image;
3. **Deploy to staging VPS** — deployment на тестовый VPS и post-deployment smoke test.

---

## Когда запускается workflow

Workflow запускается:

- при каждом `push` в любую ветку;
- при создании и обновлении Pull Request, направленного в `main`.

При этом publish и deployment выполняются только при следующих условиях:

- событие — `push`;
- ветка — `main`;
- CI job завершился успешно;
- Docker image успешно опубликован в GitHub Container Registry.

Для feature-веток и Pull Request выполняется только CI job. Docker image не публикуется и staging deployment не запускается.

---

## Общая схема

```text
Feature branch / Pull Request
        |
        v
Tests
        |
        v
Bandit SAST
        |
        v
Gitleaks secret scanning
        |
        v
pip-audit SCA
        |
        v
Docker build validation
        |
        v
Upload security reports artifact
```

```text
Successful push to main
        |
        v
Publish Docker image to GHCR
        |
        v
Deploy exact SHA-tagged image to staging VPS
        |
        v
Wait for Docker health-check
        |
        v
External smoke test: GET /health
```

---

## Job 1: Tests, security scans and Docker build

Первый job выполняет Continuous Integration.

### Последовательность шагов

| Шаг | Назначение |
|---|---|
| Check out repository | Загружает исходный код в GitHub Actions runner |
| Set up Python | Устанавливает Python и использует pip cache |
| Install dependencies | Устанавливает зависимости приложения и development-инструменты |
| Create reports directory | Создаёт каталог `reports/` для JSON-отчётов |
| Run application tests | Запускает автоматические тесты pytest |
| Run Bandit SAST scan | Проверяет Python-код на потенциально небезопасные паттерны |
| Set up Go for Gitleaks | Подготавливает окружение для установки Gitleaks |
| Run Gitleaks secret scan | Проверяет файлы и Git-историю на потенциальные секреты |
| Run pip-audit dependency scan | Проверяет зависимости на известные vulnerabilities |
| Build Docker image | Проверяет, что Docker image приложения успешно собирается |
| Upload security reports | Сохраняет доступные отчёты как GitHub Actions artifact |

### Проверка Git-истории Gitleaks

В checkout используется настройка:

```yaml
fetch-depth: 0
```

Она загружает полную Git-историю, а не только последний commit.

Это важно для secret scanning: секрет может быть удалён из текущей версии файла, но остаться доступным в старом commit. Gitleaks получает полную историю и запускается без параметра `--no-git`.

---

## Security reports artifact

В CI создаются JSON-отчёты:

```text
reports/bandit-report.json
reports/gitleaks-report.json
reports/pip-audit-report.json
```

Они загружаются в GitHub Actions как artifact:

```text
security-reports
```

Загрузка artifact выполняется с условием:

```yaml
if: always()
```

Поэтому GitHub Actions пытается сохранить отчёты даже в случае падения проверки.

Если workflow остановился на раннем этапе, artifact может содержать только отчёты, которые успели сформироваться до ошибки. Каталог `reports/` исключён из Git через `.gitignore`, поэтому результаты отдельных запусков не засоряют репозиторий.

---

## Почему Docker image собирается дважды

Docker build выполняется в двух разных целях.

### В CI job

```text
Docker build validation
```

Image собирается для проверки:

- Dockerfile не содержит ошибок;
- зависимости устанавливаются корректно;
- application code копируется в image;
- образ можно воспроизводимо собрать в изолированном окружении.

В этом job image не публикуется.

### В publish job

После успешного CI отдельный job повторно собирает image, присваивает version tags и публикует его в GitHub Container Registry.

Так publish и deployment выполняются только после успешного прохождения тестов и security-проверок.

---

## Job 2: Publish Docker image to GHCR

Job **Publish Docker image to GHCR** зависит от успешного выполнения CI:

```yaml
needs: ci
```

Он запускается только для `push` в `main`.

### Что делает job

1. Выполняет checkout исходного кода.
2. Аутентифицируется в GitHub Container Registry через встроенный `GITHUB_TOKEN`.
3. Собирает Docker image.
4. Публикует image в GHCR.
5. Добавляет metadata labels с источником и commit SHA.

### Docker image tags

Каждая опубликованная версия image получает два тега:

```text
latest
sha-<full-commit-sha>
```

Например:

```text
ghcr.io/fitmesec/secure-cicd-pipeline:latest
ghcr.io/fitmesec/secure-cicd-pipeline:sha-78fed7c1a9bfb1ef56b16363b2fc6b93df712531
```

Тег `latest` удобен для быстрого запуска актуальной версии.

Тег `sha-<full-commit-sha>` фиксирует конкретную версию исходного кода и используется при deployment. Это делает deployment воспроизводимым: можно определить, какой именно commit был развёрнут на staging VPS.

---

## Job 3: Deploy to staging VPS

Job **Deploy to staging VPS** зависит от успешной публикации image:

```yaml
needs: publish-image
```

Он запускается только для `push` в `main`.

### Что делает deploy job

1. Получает приватный SSH-ключ из GitHub Actions Secret.
2. Создаёт временный SSH key file на GitHub runner.
3. Добавляет host key staging VPS в `known_hosts`.
4. Подключается к VPS как отдельный пользователь `deploy`.
5. Выполняет аутентификацию в GitHub Container Registry.
6. Передаёт переменную `IMAGE_TAG` со значением:

   ```text
   sha-<full-commit-sha>
   ```

7. Выполняет:

   ```bash
   docker compose pull
   ```

8. Запускает новую версию приложения:

   ```bash
   docker compose up -d --wait --remove-orphans
   ```

9. Выводит состояние сервисов через:

   ```bash
   docker compose ps
   ```

### Использование точного SHA-tag

На staging VPS Docker Compose использует образ через переменную:

```text
IMAGE_TAG
```

В `compose.yaml` задана логика:

```yaml
image: ghcr.io/fitmesec/secure-cicd-pipeline:${IMAGE_TAG:-latest}
```

Deployment job передаёт значение:

```text
IMAGE_TAG=sha-<full-commit-sha>
```

Поэтому staging VPS скачивает и запускает image конкретного commit, а не только текущий `latest`.

---

## Docker health-check

В `compose.yaml` определён health-check, который обращается к локальному endpoint:

```text
http://127.0.0.1:8000/health
```

Deployment использует:

```bash
docker compose up -d --wait --remove-orphans
```

Параметр `--wait` заставляет Docker Compose дождаться успешного health-check и статуса:

```text
healthy
```

Если контейнер не проходит health-check, deploy job завершается с ошибкой.

---

## External smoke test

После успешного Docker health-check GitHub Actions выполняет внешний HTTP smoke test:

```text
GET http://<VPS_IP>:8000/health
```

Для проверки используется `curl --fail` с повторными попытками.

Логика smoke test:

- `--fail` завершает шаг ошибкой при HTTP 4xx или 5xx;
- `--retry` повторяет запрос, если приложение ещё запускается;
- `--retry-connrefused` обрабатывает короткую задержку открытия порта контейнером;
- `--connect-timeout` ограничивает время подключения;
- `--max-time` ограничивает время одной попытки.

Smoke test подтверждает, что после deployment приложение доступно извне и отвечает на базовый endpoint.

---

## Staging environment

Deployment выполняется в изолированную staging-среду, а не в production.

Staging VPS включает:

- Linux VPS;
- Docker Engine;
- Docker Compose;
- отдельного пользователя `deploy`;
- SSH-доступ по ключу;
- Docker Compose configuration;
- порт `8000` для тестового API;
- Docker health-check;
- внешний smoke test после deployment.

Доступ VPS к GitHub Container Registry настраивается отдельно. При использовании приватного Docker image требуется аутентификация с правом чтения пакетов.

Токены, приватные SSH-ключи, IP-адреса, пароли и другие sensitive values не хранятся в Git-репозитории. Для них используются GitHub Actions Secrets.

---

## Политика результата pipeline

Pipeline считается успешным, если:

- все pytest-тесты прошли;
- Bandit не вернул блокирующих findings;
- Gitleaks не нашёл потенциальных секретов;
- `pip-audit` не нашёл известных уязвимостей согласно политике проекта;
- Docker image успешно собрался;
- image успешно опубликован в GHCR;
- staging VPS скачал нужный SHA-tag image;
- контейнер получил Docker health status `healthy`;
- внешний endpoint `/health` ответил успешно.

Если любой обязательный этап завершается ошибкой, соответствующий job становится красным. Публикация image и deployment не запускаются, если CI не завершился успешно.
