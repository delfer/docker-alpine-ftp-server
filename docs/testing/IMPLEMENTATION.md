# Инструкция для реализации тестов

## Задание следующей модели

Реализовать автоматические тесты по [catalog.json](catalog.json) и [CASES.md](CASES.md), начиная с первой очереди ниже. Сохранить ID в именах параметров и JUnit. Не менять product-код, чтобы скрыть неудачный тест. Известные дефекты выделять точным precondition и strict xfail с ID, ожидаемой причиной и ссылкой; новые ошибки должны падать. Не объявлять все 341 сценарий implemented после одних восьми smoke-тестов.

Прочитать README.md и RESEARCH.md этой папки. Текущий контракт привязан к указанному SHA. Перед реализацией на новом SHA сверить изменения и состояния открытых PR. Спецификация не требует обращаться к настоящему ACME, публиковать Docker images, писать в issues/PR или менять firewall хоста.

Предлагаемый стек: Python 3.12+, pytest, стандартные ftplib/ssl/socket/subprocess/hashlib, Docker CLI; cryptography для сложных certificate fixtures при необходимости. curl/libcurl — независимый контроль. Версии зависимостей фиксировать в test requirements. Для текущей задачи эти тестовые зависимости и suite не добавлялись.

## Структура будущей suite

```text
tests/
  conftest.py
  support/
    docker.py          # argv subprocess, resource ownership, logs, bounded cleanup
    clients.py         # exact PASV/EPSV/PORT/EPRT, TLS reuse, redacted transcript
    fixtures.py        # users, payloads, filesystem, certificates, custom config
    topology.py        # direct, published/NAT router, IPv6, fault injection
  integration/
    test_modes.py
    test_users.py
    test_files.py
    test_permissions.py
    test_tls.py
    test_network.py
    test_lifecycle.py
    test_config.py
    test_concurrency.py
    test_failures.py
  compatibility/
  coverage-manifest.json
```

Это предложение структуры, не уже существующие файлы. Тестировать поведение запущенного образа, а не только mock вызовов adduser или совпадение текста shell-script. Для сложного fail path допускается fault fixture, но позитивный сценарий обязан пройти на настоящем образе.

## Образ и Docker endpoint

Собирать именно local checkout. В обычной среде:

```bash
docker build -t ftp-under-test:local .
IMAGE_REF=ftp-under-test:local
```

В managed cloud сначала проверить локальный daemon, убрав возможные endpoint overrides:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock info
```

Не печатать Docker config или весь env. В облаке для networked RUN steps нужен session CA: передать его BuildKit secret и настроить SSL_CERT_FILE/GIT_SSL_CAINFO **временно на время RUN**, в обоих stages. Не отключать TLS verification и не класть session CA в runtime layer. Исследовательская сборка использовала временную копию Dockerfile только с такими trust-настройками; исходный Dockerfile не менялся.

Прокси предназначен для HTTP(S) загрузок зависимостей. FTP-пакеты теста идут внутри собственных Docker-сетей; убрать у клиентов FTP_PROXY/ALL_PROXY, если они заставляют тест идти через внешний прокси. Не подменять platform HTTP proxy ради сборки.

Сохранять git SHA, image ID, base digest, client digest, Docker/Compose/kernel/CPU, APK versions, Python/OpenSSL versions. `latest` и неприкреплённые APK mirrors дают разные dependency snapshots даже на одном git SHA.

## Общий контракт fixtures

Каждый независимый startup case получает новый container. По умолчанию restart policy=no: автоматический restart маскирует #48. Один build на session, контейнеры/сети/volumes — по тесту или по безопасной группе. Не переиспользовать мутированный passwd/shadow/config между case.

Все Docker objects помечать label `ftp-test.run=<uuid>`. Cleanup в finally удаляет только IDs текущего запуска. Нельзя использовать global prune/killall/docker rm по общему шаблону. Два parallel workers должны иметь разные networks, paths, names и опубликованные порты. Не фиксировать host2121 глобально для parallel suite.

Таймауты:

| Стадия | Базовый deadline |
| --- | ---: |
| Boot с одним/несколькими users | 30 s |
| Control connect/read | 5 s |
| Data connect/handshake | 5 s |
| Обычная операция с небольшим payload | 10 s |
| 16 MiB stream | 60 s |
| 100-user boot | 120 s |
| Graceful docker stop | Docker -t10, ожидание завершения до его kill deadline |
| Специальные idle/data timeout cases | custom config 3 s + bounded tolerance |

Использовать monotonic deadlines, а не `sleep(30)`. Poll ≤0.2 s; после любого промежуточного успеха проверять container state. Для базовых protocol tests сначала дождаться создания pidfile и идентификации main listener через process/socket state, затем control/login/data. Проверить стабильность минимум 5 s после ready, не исключая начало этого окна из измерения.

В LIFE-004 намеренно подключаться сразу: обычный readiness probe сам способен попасть в startup race. Не исправлять этот тест задержкой или retry. Чисто протокольная исследовательская проба имела 3 s стартовую паузу для отделения mode-проверки от этой гонки; production readiness на такой паузе строить нельзя.

Негативный startup case оценивает функциональную готовность отдельно от exit status: сейчас сломанный daemon может дать exit0 либо временно Up. Желаемый nonzero — hardening, а не уже существующая гарантия.

## Users и filesystem fixtures

Фиктивные пароли генерировать/передавать через subprocess env, без shell command interpolation. В отчёте использовать роли users и редактировать PASS. Не выводить целиком USERS.

| Identity profile MX-CORE | USERS |
| --- | --- |
| auto | alice\|test-pass-a |
| uid-new-gid | alice\|test-pass-a\|\|10000\|12000 |
| uid-existing-gid | alice\|test-pass-a\|\|10000\|82 |
| two-auto | alice\|test-pass-a bob\|test-pass-b |
| two-explicit-shared-gid | alice\|test-pass-a\|\|10000\|12000 bob\|test-pass-b\|\|10001\|12000 |
| mixed-explicit-auto | alice\|test-pass-a\|\|10000\|12000 bob\|test-pass-b |

Для всех пользователей профиля выполнять login и roundtrip, не только для alice. В shared GID профиле требовать правильное групповое поведение, не полную приватность друг от друга. Для числового ownership использовать stat numeric UID/GID и /etc/passwd/group; имя группы на host может отличаться.

`layer` — home без mount. `bind-rw` — отдельный пустой host tmpdir mounted на `/ftp`, homes ниже него. `named-volume` — отдельный named volume на `/ftp`. Это намеренно создаёт различные условия существования parent: adduser может заранее создать home и обойти эффект mkdir -m. Не делать chmod750 в fixture после entrypoint: это замаскирует FS-003.

Для custom home/recovery fixture создать эквивалентный mount на `/home`, USERS указывает `/home/alice/dir`. Для read-only fixture заранее наполнить каталог с корректными UID/GID, затем mount ro; иначе ошибка startup chown смешается с проверкой FTP read-only. Снимок файлов до/после: relative name bytes, type, mode, uid, gid, size, mtime, SHA256. Ownership старых nested files не исправлять рекурсивно.

Payload: детерминированный PRNG с фиксированным seed и уникальным индексом каждого chunk; исходный ожидаемый SHA считать независимо, сравнить с диском сервера и RETR. Для небольшого файла дополнительно сравнивать bytes. Равенства только длины недостаточно. Для large streaming не загружать весь файл в RAM. Исследовательский smoke использовал 4352 bytes; будущие тесты используют набор MX-PAYLOAD.

## Клиент: запретить скрытый fallback

ftplib.set_pasv(False) выбирает active, но не задаёт отдельно PORT/EPRT. IPv4 ftplib обычно выбирает PASV/PORT. Нужен helper, который принудительно посылает **ровно нужный verb**.

PASV: `sendcmd("PASV")` → parse227 → TCP ровно к advertised host/port. Python по умолчанию может игнорировать IPv4 адрес из 227, и это скрывает неправильный ADDRESS. Для этих тестов override makepasv либо явно включить trust_server_pasv_ipv4_address. Обязательно проверить raw227 отдельно от успешного transfer.

EPSV: `sendcmd("EPSV")` → parse229 → host из control peer, port из 229. Не подменять EPSV на PASV при неудаче.

PORT: открыть listening socket на реальном IPv4 клиента, передать 4 octets и 2 octets port, отправить transfer command, принять server TCP. EPRT: тот же listener, но `EPRT |1|address|port|`. IPv6 — только custom IPv6 fixture с AF2. Закрыть listening socket в finally, включая send-command failures.

Транскрипт хранит команды/коды ответов, выбранный mode, socket endpoints и negotiated TLS. PASS и любые secrets редактируются до записи. После data EOF обязательно прочитать финальный response: предварительный 150 и существующий zero-byte file не доказывают успех. Для Java требуется completePendingCommand.

Активный TCP подключает сервер, но **TLS-клиентом data channel остаётся FTP-клиент**, даже когда тот принимает TCP. Не применять TLS server_side=True к клиентскому active listener.

Для независимого curl/libcurl-клиента задать режимы явно и сверять redacted verbose trace:

| Профиль | Параметры curl |
| --- | --- |
| PASV | --ftp-pasv --disable-epsv --no-ftp-skip-pasv-ip |
| EPSV | --ftp-pasv; проверить, что EPSV принят и fallback PASV отсутствует |
| PORT | --ftp-port - --disable-eprt |
| EPRT | --ftp-port -; проверить, что EPRT принят и fallback PORT отсутствует |
| Explicit FTPS1.2 | URL ftp://ftp.test; --ssl-reqd --tlsv1.2 --tls-max 1.2 --cacert test-ca.pem |
| Explicit FTPS1.3 | URL ftp://ftp.test; --ssl-reqd --tlsv1.3 --tls-max 1.3 --cacert test-ca.pem |

`--upload-file payload.bin` выполняет STOR, обычный GET того же URL — RETR, URL каталога — listing. После каждой операции сравнить SHA256, проверить delete отдельной FTP-командой. URL ftps:// у curl обычно означает implicit TLS и не заменяет explicit test. FTP URL path semantics и escaping UTF-8/пробелов проверять отдельно; для credential fixtures использовать временный0600 curl config/stdin, не публиковать raw verbose trace с PASS.

### TLS reuse

На исследованной сборке стандартный FTP_TLS без reuse получает 522. Минимальная идея клиента, проверенная в исследовании:

```python
class ReuseFTP_TLS(ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            try:
                conn = self.context.wrap_socket(
                    conn,
                    server_hostname=self.host,
                    session=self.sock.session,
                )
            except BaseException:
                conn.close()
                raise
        return conn, size
```

Совместить это с exact makepasv/makeport, не вызвать повторно стандартный FTP_TLS.ntransfercmd и не обернуть socket дважды. Использовать один SSLContext для control и data. Доверять локальному test CA, verify hostname=ftp.test; network alias должен резолвиться. Сначала AUTH TLS, затем login, PBSZ0/PROTP. Не снимать require_ssl_reuse на сервере ради успеха позитивного теста.

TLS1.2 context: minimum_version=maximum_version=TLSv1_2. TLS1.3: отдельный context с pin1.3; прочитать control replies после login/PROTP, чтобы получить session tickets; проверить data transfer, а не один auth(). В probe с Python3.12 механизм session= прошёл на 1.2 и 1.3. Отдельный негатив использует обычный FTP_TLS без reuse.

Data assertions: SSLSocket, negotiated version, при доступности session_reused; для plain — обычный socket. Положительный TLS тест не использует CERT_NONE. Негативные проверки старых протоколов требуют клиента, способного отправить соответствующий ClientHello: ошибка local no protocols не является ответом сервера.

## Certificates

Каждый запуск использует локальные временные ключи. Базовый fixture: CA и leaf с SAN DNS:ftp.test, key RSA2048, validity на период теста; cert/key mounted ro. Простая исследовательская проба использовала самоподписанный SAN certificate как trust anchor. Для chain case нужен root→intermediate→leaf.

Варианты: missing/directory/empty/invalid PEM, mismatch pair, encrypted key, ECDSA, expired, not-yet-valid, untrusted issuer, wrong hostname, fullchain и Let's Encrypt symlink layout. Expiration проверяет клиент: сам сервер может успешно стартовать с expired cert. Passphrase нельзя ждать интерактивно.

Реальную выдачу/renewal Let's Encrypt не вызывать. Symlink case создаёт свои `live`/`archive` каталоги. Renewal case меняет локальный fixture и сравнивает fingerprint новых соединений до/после restart.

## Топологии

### Direct bridge

Своя Docker user-defined network; server alias ftp.test, Python client в другом контейнере той же сети. ADDRESS=ftp.test. Control21, passive21000..21010, client active listener на случайном high port. При TLS сертификат SAN ftp.test. Для этого варианта вообще не нужны опубликованные host ports.

В managed cloud Docker daemon может жить в другом network namespace: отсутствие доступа агента к 172.x container IP не значит, что FTP сломан. Запуск клиента внутри Docker-сети обязателен.

### Published ports и router для MX-CORE

Лёгкий host smoke публикует свободный loopback control→21 и identity passive range; внешний ADDRESS должен быть достижим клиентом. Этого достаточно для passive compat, но active callback из-за NAT может получить peer-IP mismatch.

Для полного MX-CORE published-router использовать две изолированные сети front/back и отдельный router container с NET_ADMIN и ipv4_forward. Клиент только во front, сервер только в back. Router front address — ADDRESS и control endpoint. DNAT control21 и весь passive range на server back address, сохранять одинаковые passive port numbers.

Маршрут server→front должен идти через router; control source IP клиента сохраняется, чтобы server IP check оставался включён. Для новых active TCP flow source server→front преобразуется в router front address, чтобы client remote verification совпадала с control peer. Client advertises свой достижимый front address. Явно проверить обе стороны packet capture. Не выполнять слепой MASQUERADE control в back: тогда сервер увидит router IP вместо клиента и PORT/data IP checks будут проверять другую ситуацию.

Тестовый router и при необходимости netns setup-helper получают дополнительные capabilities; product container не требует новых capabilities для FTP. Конкретные свободные private subnets выбирать проверкой overlap. Router rules удаляются вместе с его контейнером. Никаких iptables/firewalld mutations в namespace хоста.

Failure cases: wrong/missing ADDRESS, DNS changes, unexposed ports, mismatched ranges, intentionally blocked callbacks, different control/data IP, exhausted passive listeners. Для exhaustion сначала установить контроль с одним портом: удержать PASV listener/data, создать вторую session, затем освободить. TIME_WAIT сам по себе не равен занятости всего server range.

IPv6 fixture включается явно и требует listen=NO/listen_ipv6=YES; direct IPv4 default не выдавать за IPv6 поддержку. FXP — два server и третий controller, только явный custom profile; default IP checks не выключать для обычной suite.

## Рецепты

Рецепт — общая последовательность; действия каждого case добавляют конкретные inputs и негативные шаги. Для mode_set=self использовать **все** перечисленные в case варианты. Если security не указан и случай может влиять на обе службы, повторить на FTP и FTPS12. Если проверяется data path — PASV/EPSV или PORT/EPRT выбираются по действиям, а для общих свойств все 4 в обоих security. Startup malformed-input cases не требуют умножения на data verbs.

| Рецепт | Как проводить |
| --- | --- |
| R-BUILD | Build; inspect image; runtime command probes; full smoke на соответствующей архитектуре; сохранить manifest. |
| R-USERS | Fresh container с одним конкретным USERS; custom command inspect passwd/group/id/stat; отдельный service run для login всех expected users; проверить и отсутствие unexpected users. |
| R-CONTROL | Выбрать FTP/FTPS control fixture; raw commands и точные states; после любого отказа новый корректный login, listener PID и RestartCount. |
| R-ROUNDTRIP | Для каждого user STOR→server stat/hash→LIST+NLST→RETR/hash→rename→DELE; MKD/CWD/RMD; QUIT; новый login; проверить ownership. |
| R-DATA | Подготовить точные пути/bytes/mtime до операции; выполнить только нужные FTP verbs; прочитать final response; сравнить bytes и filesystem diff. |
| R-MODE | Запретить fallback; записать выбранный verb, advertised endpoint, фактический TCP direction; выполнить upload/download/list и переходы из case. |
| R-NET | Сначала рабочий control+data контроль; изменить один address/range/route input; проверить raw227/229 и endpoints; отрицательный outcome с deadline; восстановить и проверить снова. |
| R-TLS | Локальные cert fixtures, verified context, exact protocol version; положительный reuse; отдельные negative contexts/commands; проверить отсутствие plain downgrade. |
| R-FS | Snapshot content/mode/numeric IDs; login owner и second user в обе стороны; allowed read/write плюс каждый forbidden mutation; после проверить отсутствие изменений. |
| R-LIFECYCLE | Снять container/listener/supervisor/session PIDs; event/restart/kill по точному PID; events+exit+duration; затем ready/login/roundtrip и persistent file hash. |
| R-CONFIG | Копия original config с явной одной разницей, root-owned bind:ro; задавать dedicated env отдельно; assertion по effective protocol, не только config text. |
| R-OBS | Canary credentials, известные operations; bounded log collection; проверить operation evidence и отсутствие canary secrets; после нагрузки resource baseline. |
| R-DOC | Разобрать example без исполнения placeholder/ACME; actual Compose config/env и filesystem; выполнить локальный equivalent и проверить login/data. |
| R-CI | Static workflow validation плюс failing test fixture; не публиковать image; проверить propagated exit и отсутствие secrets на PR. |
| R-COMPAT | Точный client/version/options; те же deterministic fixtures; no silent fallback; hash и final response; unsupported feature — explicit capability result. |
| R-FUTURE | До появления фичи только current-API characterization; затем отдельные acceptance tests для принятого поведения, не активировать чужой PR автоматически. |
| R-CONCURRENT | Barrier после open data/до payload; независимые клиенты/processes; выполнять одновременно, сравнить отдельные hashes, state и logs; controlled limits. |
| R-FAULT | Barrier на известном количестве server-confirmed bytes; один fault; bounded error/finish; partial snapshot; новое корректное соединение и повторный transfer. |

Concurrent tests не строить на случайном sleep. Использовать barriers/events и явные состояния socket. Обычный QUIT и graceful TLS shutdown отделять от RST/timeout. При fault не всегда можно знать точный ответ до выполнения characterization: фиксировать server outcome, но не принимать любое исключение за PASS.

## Ожидания и известные дефекты

`contract` → обычный assert. `known-defect` → сначала показать воспроизведение; временный strict xfail только для точного условия и ожидаемого симптома, с источником/ID. Изменился симптом — FAIL; XPASS требует снять marker. Например, неверный password не должен попасть под xfail mixed-UID.

`characterization` → сначала записать baseline и объяснить, какие invariants обязательны: server жив, unrelated files целы, нет silent success. Не превращать небезопасное поведение в желаемый контракт. После выбора политики разделить baseline и regression.

`hardening` → отдельная очередь desired-behavior тестов, которые могут обнаружить текущую ошибку. `decision`/`future` не запускать как будто фича реализована. В coverage manifest писать pending reason, необходимую фичу/решение и ID; отсутствие реализации не выдавать за passed/covered.

Known risk групп: stale UID_OPT/GROUP_OPT, home2755, custom-home restart, default no chroot, early startup exit, Compose literal quotes, hidden dotfiles, отсутствие CONF_/_FILE/LISTEN_PORT. RESEARCH.md отделяет измеренные факты от гипотез.

## Матрицы и отчёт покрытия

Развернуть axes из catalog.json через itertools.product и проверить counts288/72/96/24/24/4. Стабильный node ID содержит matrix+values, например `MX-CORE[ftps12-eprt,uid-existing-gid,named-volume,published-router]`. Не применять случайный pairwise reducer к этим шести product.

Все варианты, перечисленные словами в case actions, развернуть в именованные pytest parameters. Например, все 6 перестановок GRP-009 и каждую ошибочную форму NET-007. Mode sets — явные списки, не выбор «любого из». Не умножать pure startup syntax errors на 8 одинаковых data-mode тестов.

Для дополнительных огромных сочетаний допустим детерминированный pairwise-набор сверх обязательных матриц: clients × architectures × topology × TLS version × file size. Сохранить generated rows и pair-coverage отчёт, чтобы fast model не называла pairwise полным декартовым покрытием.

coverage-manifest.json на каждый case хранит: ID, implemented node IDs, expanded input variants, status, last outcome, skip/xfail reason, dependency/manual runner, источники. Полезные markers: smoke, integration, tls, active, passive, regression, hardening, slow, architecture, manual, future. Один P0 manual case не заставляет запускать Windows VM на каждом Linux PR.

Артефакты failure: redacted transcript, complete stdout/stderr, Docker state/events, ps parent/UID и pidfile, sockets/endpoints, sanitized effective config, filesystem snapshot/diff, JUnit. Не печатать shadow, password hashes, private keys или весь env. Packet captures только собственных fixtures, без стороннего трафика.

## Очереди реализации и приёмка

**Первая очередь:** Docker build/cleanup, exact client, CA, core8 + TLS13, AUTH негативы, GRP-007/008/009, FS-003/004, LIFE-002/004/017, DOC-003/004/005. Должны обнаруживаться непустой broken upload, неправильный PASV IP и потерянный second user.

**Вторая очередь:** все contract P0/P1, шесть матриц, остальные filesystem/data/TLS/network/lifecycle cases; truthful strict xfail по доказанным дефектам. DATA scenarios сначала на direct bridge, затем MX-CORE router.

**Третья очередь:** concurrency/fault injection, nightly100 starts/1000 transfers, старые протоколы,4 architectures, независимые clients и platform cases. Отдельный manual document для RHEL/Desktop/Windows и >4GiB.

**Четвёртая очередь:** decisions/hardening fixes, затем принятие FUT-функций. У всех 341 IDs есть выполненный тест либо конкретный pending/manual reason. У 6 matrices проверены точные counts; ни один unsupported-tooling skip не назван проверкой сервера. На PR runtime suite вызывается после build, failures доходят до CI; publish запускается только существующей release политикой.
