# Docker integration tests

Only test code and GitHub test jobs are changed. Application failures are ordinary
failures: there are no xfail markers, retries, continue-on-error or application
patches in this suite.

Requirements: Docker (Linux containers), Python 3.12+, OpenSSL CLI, access to the
Python client image. No host pip dependencies.

Run from the repository root:

    docker build -t ftp-under-test:local .
    docker pull python:3.12-alpine
    python3 tests/run.py --image ftp-under-test:local

For a managed local daemon set DOCKER_HOST=unix:///var/run/docker.sock explicitly.
The runner preserves DOCKER_HOST; it clears saved Docker context/TLS selectors.
An alternative client image can be passed with --client-image.

The client runs in an isolated Docker network, so active callbacks work even
when the host cannot reach container IP addresses. Fixtures are copied through
Docker rather than bind-mounted. Each server/network/client has a UUID and is
removed in finally. Credentials and certificates are disposable test data.

The default run exercises plain FTP, explicit TLS1.2 and TLS1.3 against all four
data verbs (PASV/EPSV/PORT/EPRT), exact bytes at nine sizes (including16MiB),
twelve pathname classes, overwrite, append, REST, rename, missing files,
directories, mode changes, repeated transfers, concurrent sessions, login errors,
protocol errors, passive ranges, dotfiles, no-chroot characterization, TLS
verification and reuse rejection. Read-only configurations run separately.
UID/GID checks include all six permutations of auto/new/existing-group accounts;
private home permissions and listener-death supervision are asserted separately.

Results are written to test-results/ (override with --output): JUnit XML,
JSON case outcomes, client output and server logs. Exit status is nonzero when
any assertion, fixture startup or client process fails. A broken startup is
reported as a suite failure; tests which could not run are not reported as passed.
The runner continues to independent server profiles after failures.

This executable suite is a subset of the research catalogue in docs/testing:
it does not implement all341 specifications or the full508 scenario products.
Router/NAT, bind/named-volume products, GUI clients, ARM execution, stress100
starts, future features and decision cases remain in that catalogue. A green
run must not be described as full catalogue coverage.

GitHub: the existing publish workflow runs integration tests before its existing
publish job. The additional ftp-tests workflow runs for test/workflow pushes,
daily and manually; it never publishes an image. Artifacts upload even on
failure. A failing application test intentionally blocks the existing release
dependency, without modifying the application's behavior.
