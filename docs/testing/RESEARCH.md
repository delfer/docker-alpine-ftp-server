# Результаты исследования

## Область и источники

Репозиторий: [delfer/docker-alpine-ftp-server](https://github.com/delfer/docker-alpine-ftp-server). Исследуемый SHA: `8989ee25e7bc6ff12bc9af41ee9433737ac3e842`, дата коммита 1 марта 2025. GitHub master на 12 ноября 2026 указывает на тот же SHA. В рабочем дереве до добавления этой документации изменений не было; AGENTS.md не найден.

Прочитаны README.md, Dockerfile, start_vsftpd.sh, vsftpd.conf и .github/workflows/docker-publish-image.yml целиком. Изучена история 47 коммитов, в том числе реализация supervision, изменение default user, reuse существующей группы 82, TLS и отмена chroot. Через GitHub connector получены все 53 issues и 32 PR, полные bodies, PR diffs и 182 комментария/ревью. Номера 1..85 покрыты полностью; нет выборки только по словам TLS/passive.

[Реестр](REVIEWED-SOURCES.md) сохраняет связь каждого материала с тестами; [sources.json](sources.json) фиксирует состояния и refs. Открыты PR45/81 (CONF_) и 73 (USERS_FILE). Отдельно прочитаны README и pidproxy.c зависимости на pinned commit `193e5080e3e9b733a59e25d8f7ec84aee374b9bb` — это объясняет watchdog, signals и polling fallback. Остальной upstream vsftpd не объявляется полностью исследованным: тесты проверяют реальный packaged daemon.

## Устройство и границы API

| Компонент | Реальное поведение | Что проверять |
| --- | --- | --- |
| Dockerfile1–20 | Два stages на Alpine3.19; сборка pinned pidproxy; runtime vsftpd+tini | Build, четыре архитектуры, TLS libraries, runtime utilities |
| Dockerfile22–27 | COPY скрипта/config; EXPOSE21 и 21000..21010; tini→start script | Permissions/shebang, image metadata, отсутствие automatic VOLUME |
| start_vsftpd.sh4 | Удаляет accounts, чья строка passwd содержит /ftp/ | Cleanup substring, default/custom home restart |
| строки 19–56 | USERS split по shell IFS, поля через cut, addgroup/adduser, mkdir/chown | Parse, UID/GID, многопользовательские permutation tests |
| строки 59–69 | Defaults MIN/MAX21000/21010, optional ADDRESS | Raw227/229, DNS, диапазон, NAT |
| строки 71–73 | Непустой TLS_CERT **или** TLS_KEY включает forced TLS logins+data | Cert errors, downgrade rejection, protocol versions |
| строки 75–82 | Custom argv после init либо background vsftpd + pidproxy pidfile true | Custom-command exit, правильный main PID, startup/stop |
| vsftpd.conf | Local users/write YES, anonymous NO, umask022, active source20, passive YES, IPv4 listen, background YES, logs→PID1 stdout | File operations, permissions, mode combinations, diagnostics |
| workflow | PR test job делает только docker build, если docker-compose.test.yml отсутствует | Runtime tests действительно запускаются и ошибки распространяются |

Runtime env API — **шесть переменных**: USERS, ADDRESS, MIN_PORT, MAX_PORT, TLS_CERT, TLS_KEY. BASE_IMG — build argument. Никакого переключателя ACTIVE/PASSIVE нет: обе возможности одновременно доступны; нужный способ выбирает клиент.

FTPS — explicit AUTH TLS на control21. При TLS vars обязательны защищённые login и data. Implicit FTPS990 и SFTP22 не реализованы. Certificate/key надо предоставить внутри контейнера; генерации, certbot или renewal-демона внутри image нет.

CONF_, CONF_SET_PARMS, USERS_FILE, LISTEN_PORT и SSL=true не обрабатываются текущим entrypoint. TZ не имеет отдельной реализации/setup-timezone; поведение libc TZ без zoneinfo не равно обещанной фиче. Дополнительные настройки делают через замену vsftpd.conf; CLI -o options entrypoint могут перекрывать file values.

## Доказанные наблюдения

Сборка выполнена 12 ноября 2026 на Linux x86_64, Docker29.9.2, kernel6.18.57. Собран checkout без product-изменений; для TLS-inspecting cloud proxy во временный Dockerfile добавлены только BuildKit CA mount и trust env на сетевых RUN. Runtime Alpine3.19.7, vsftpd3.0.5-r2, tini0.19.0-r2. Exact local image ID: `sha256:f14bff95c3b17d9ffa16d3e409b08f5fd6e80eb15bfafef912aaed6c7165e542`. Это локальный ID, не опубликованный digest.

Проверки protocol modes использовали отдельный Python3.12-alpine client container в одной user-defined Docker-сети с server. ADDRESS=ftp.test, cert SAN DNS:ftp.test, verified TLS context. Клиент принудительно выбирал verb, повторно использовал TLS control session для data и не делал fallback. Payload4352 bytes, полный range0..255 повторён 17 раз; сравнивались bytes, наличие в NLST, удаление. TLS1.2 и 1.3 были pin каждого отдельного запуска.

| Проба | Результат | Связанные кейсы |
| --- | --- | --- |
| Build текущего checkout | Успешен; image запускается | BLD-001 |
| Published-port FTP smoke | Login, passive upload/list/download/delete, byte equality, invalid password530 | AUTH-001/002, DATA-001 |
| FTP: PASV/EPSV/PORT/EPRT | Все 4 успешны | MODE-001, DATA-001 |
| FTPS TLS1.2: те же 4 | Все 4 успешны | TLS-017/024 |
| FTPS TLS1.3: те же 4 | Все 4 успешны | TLS-018, MX-TLS13 |
| Legacy1.0/1.1 | Server protocol-version alert; ClientHello отправлен capable client | TLS-019 |
| Обычный FTP_TLS без reuse | 522 SSL connection failed: session reuse required | TLS-025 |
| Explicit UID затем auto user | Second account отсутствует; adduser uid10000 in use; /ftp/second root-owned | GRP-007 |
| GID82 без UID | Игнорируется; account получил UID/GID1000 | GRP-010 |
| Два auto users, fresh parent | /ftp/alice:0750, /ftp/bob:02755 | FS-003/004 |
| Home под существующим /home | /home/alice:02755 | FS-003 |
| Default без chroot | CWD / и RETR специально созданного world-readable marker вне home успешны | FS-006 |
| Restart custom home | В повторной пробе login успешен с adduser user in use; первая попытка connect после restart получила connection refused | LIFE-007/008 |
| Раннее control connect/close при старте TLS | В одном запуске daemon/контейнер завершился с process has died, quitting после первого ответа | LIFE-004/017 |

Исследовательский raw-log итог сохранён компактно в [research-probes.json](research-probes.json). Это не pytest/JUnit report и не выполнение всего каталога. Никто не проверял в этой задаче full508 product, стресс 100 запусков, ARM targets, FXP, router faults, FileZilla/Windows/RHEL.

Первая попытка connecting прямо к container172.x из agent namespace не имела маршрута и не использовалась как доказательство ошибки server. После переноса клиента в Docker-сеть protocol checks заработали. Это отдельное требование к harness для managed cloud/DinD.

## Дефекты и риски, которые нельзя потерять при реализации

### UID_OPT/GROUP_OPT наследуются между итерациями

В конце цикла очищаются NAME/PASS/FOLDER/UID/GID, но **не UID_OPT/GROUP_OPT**. Следующая запись без UID получает предыдущий -u и -G. Измерено: first UID10000 создан; second без UID не создан из-за duplicate UID; скрипт продолжает mkdir/chown. Это не отказ FTP-протокола: account отсутствует ещё до старта daemon.

Регрессии GRP-007/008/009 должны проверять всех users и все шесть перестановок auto/new-group/existing-group. Положительный тест только одного user не обнаружит проблему. Baseline GROUP_OPT contamination частично перекрывается duplicate UID: при будущем исправлении UID отдельно убедиться, что GID тоже перестал протекать.

### mkdir -m750 -p не исправляет уже созданный каталог

PR70 добавил mkdir -m750 **после adduser**. Если parent отсутствует, adduser не создаёт home; mkdir даёт 750. Если parent существует, BusyBox adduser успевает создать home02755, а mkdir -p оставляет его mode.

Измерено с USERS=alice|test-pass-a bob|test-pass-b: первый /ftp/alice получил 750, второй /ftp/bob —2755. /home/alice под существующим /home также получил 2755. Это зависит от порядка users и mounts. Private-home test обязан проверять обе стороны доступа и существование parent. Нельзя «починить» fixture chmod750 после startup.

Политика для предсуществующих mount dirs ещё требует решения: сохранять mode владельца mount или принудительно приватизировать. Новые создаваемые homes по намерению PR70 должны быть private. Shared GID допускает group read/execute даже при 750; формулировка «ни один другой user не читает» без условия группы неверна.

### Startup supervision и исчезающий PID

Скрипт выбирает `pgrep vsftpd | tail -n1`. У vsftpd есть главный процесс и session workers; PID последнего совпадения не гарантирует listener. Ранний readiness client может добавить worker до записи файла. Реальный exit при таком сценарии наблюдён один раз; **связь с неверно выбранным PID правдоподобна, но не доказана трассировкой этого запуска**. Это не следует объявлять установленной единственной причиной #48.

В LIFE-004/017 нужны process tree, socket owner и pidfile до/после раннего client. Проверка 100 запусков без клиента отделяет другую стартовую гонку от client-induced race. Автоматический restart или sleep-before-probe маскируют дефект.

Pinned pidproxy умеет pidfd и polling fallback при EPERM/ENOSYS; сообщения #49 сами по себе не доказывают фатальную ошибку. В его коде exit при исчезновении target может быть 0. Поэтому container ExitCode0 не равно успешному startup. Проверять listener/login/data и состояние PID отдельно.

### Cleanup и restart асимметричны

Удаление ищет /ftp/ в passwd. Пользователь с home /home/alice не очищается. При restart adduser может сообщить user in use, password не переустановиться; отсутствие set -e позволяет продолжить. #38 — реальная отдельная ветвь, а не гарантированный failure любого restart.

LIFE-006/007/008 раздельно проверяют same-container restart, recreate, default/custom home, password changed вручную и credentials из env. У #8 автор проекта не обещал сохранение ручных account-изменений при recreate.

В ad hoc проверках custom home один connect через 3 s после restart получил connection refused; в следующем отдельном запуске restart/login прошли, но stderr содержал adduser user in use. В первом запуске post-restart process/log state не сохранён, поэтому точная причина отказа не установлена. Второй подтверждает, что этот warning сам по себе не гарантирует смерть daemon. Password-change ветвь пока не проверялась.

### Нет default chroot

PR22 был отменён PR24 после #23. В текущем config chroot_local_user закомментирован. UNIX permissions ограничивают доступ, но jail нет. Приватный home750 не запрещает CWD в/ или чтение world-readable файлов снаружи home.

Тест current behavior — characterization; отдельные security assertions — на custom chroot fixture и будущую выбранную политику. Повторить регрессию абсолютных путей #23: в jail /test/cf/file.zip и host-style /test/cf/file.zip могут означать разные вещи.

### Документация Compose содержит literal quotes

README пример `- USERS="one|1234"` в list-form YAML передаёт кавычки как часть value. В shell docker run кавычки имеют иную функцию. Это подтверждено #14/55/63 и прямым чтением snippet; в этой задаче исправление README не выполнялось. Положительные формы: mapping `USERS: "one|1234"` или list `- "USERS=one|1234"`.

Низкий mapping21:21 исторически интерпретировался YAML1.1 как 1281; современные Compose parsers могут вести себя иначе. Проверять actual resolved config/published port, не симулировать историческую ошибку на любой версии. README Compose snippet также не полный документ: нет services:, volumes содержит placeholder.

### Парсер и диагностика

USERS не имеет escape grammar: shell IFS делит spaces/tabs/newlines, cut делит |, unquoted expansions могут glob, echo -e может преобразовывать backslash. Cases с такими значениями требуют truthful characterization/hardening, а не обещания, что любой arbitrary password/path поддерживается.

Нет failfast/валидации для malformed IDs/users/ports; adduser/mkdir/chown/daemon могут завершиться с ошибкой, после чего скрипт идёт дальше. План отдельно задаёт желаемые fail-fast tests и текущее поведение. Invalid ADDRESS и missing cert не следует объяснять коротким паролем: password warning в README-примере не является fatal.

## Смысл остальных исторических ветвей

- #4/5: DNS ADDRESS должен работать и вместе с numeric IPv4; проверять raw227.
- #6/9/28/32/43/46/49/69/71/76: control login не доказывает data connectivity; port listener создаётся после PASV, NAT/helper/firewall и IP checks — разные причины.
- #10/18/20/66/67 и commit669039a: реальные execution checks всех заявленных architectures, не только build; зависимость pidproxy раньше использовала UPX.
- #21/31/42/64/79: числовые UID/GID, shared files и реальный read-only; user label www-data не заменяет numeric ownership.
- #33/41: timezone/DST/listing/MDTM и custom localtime; отклонённый PR41 не добавил TZ API.
- #39/45/73/75/81/84: будущие env features; держать отдельно от current contract.
- #47: dotfiles в NLST и удаление внешне «пустого» каталога; force_dot_files сейчас не включён.
- #50/51/54/57: mount сертификатов и исполняемость примеров; ACME не нужен для suite.
- #52/62: modern TLS необходимо проверять wire-level handshakes, не поиском ssl_tlsv1=NO.
- #59/74: отсутствие нежелательного anonymous volume; named/bind persistence остаётся функцией Docker.
- #68: нагрузка, tiny passive pool, logs и явно разрешённый FXP; закрытие issue после расширения ports не доказывает, что любая ошибка logs — saturation.
- #78: реальный nonempty upload, оба направления data connection и независимый legacy client; zero-byte file не считать успешным upload.
- #83: banner — custom config, а не поддержанный env.
- #85: нет project license; это документационное решение, не повод добавлять произвольную лицензию.

## Незавершённые решения

Не мешают написать current-API и regression tests: политика chmod для existing homes, default chroot, GID без UID, повторные/лишние USERS поля, shared home ownership, стабильные exit codes, env precedence при будущих CONF_, version/license policy. Соответствующие decision IDs в каталоге фиксируют вопрос и необходимые проверки; работа здесь не остановлена ожиданием этих решений.
