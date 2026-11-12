# Historical regression checks

These are behavioral checks against the supplied image, run by `tests/run.py` and
both existing GitHub workflows. A failure is an ordinary failure, with server,
client, process/socket and expected-audit artifacts alongside JUnit/JSON results.
The tests do not assert a `background=YES` configuration string. Foreground under
tini passed the earlier comparison; foreground directly as PID1 has different
signal behavior. The direct-PID1 negative control demonstrates the shutdown
regression without claiming that every foreground configuration is broken.

## History and assertions

| History | Executable protection |
| --- | --- |
| [#15](https://github.com/delfer/docker-alpine-ftp-server/issues/15), [#36](https://github.com/delfer/docker-alpine-ftp-server/pull/36): container stops on client disconnect | `disconnects-and-logs`: first QUIT, three users, 12 simultaneous sessions across PASV/EPSV/PORT/EPRT, 30 QUIT/RST disconnects, unchanged real listener and no zombies; `worker-death`: kill bob's worker while alice/charlie transfer and bob reconnects |
| [#16](https://github.com/delfer/docker-alpine-ftp-server/issues/16), [#25](https://github.com/delfer/docker-alpine-ftp-server/pull/25), #36: termination and supervision | `stop-restart`: bounded SIGTERM shutdown without fallback SIGKILL, idle and with three uploads already writing bytes; restart preserves completed files. `listener-death`: kill the actual TCP21 owner and require container/session shutdown |
| [#48](https://github.com/delfer/docker-alpine-ftp-server/issues/48): startup exits | `early-start`: prepare the client before daemon start, connect/QUIT/RST immediately, match pidfile to the owner of the listening TCP socket. Five independent containers per plain/TLS1.2/TLS1.3 profile by default. No exec readiness probe, restart policy, or retries after EOF/auth/TLS errors |
| [#7](https://github.com/delfer/docker-alpine-ftp-server/pull/7), #36, [#68](https://github.com/delfer/docker-alpine-ftp-server/issues/68): stdout/audit logs and repeated transfers | Exact counts for each user, filename and successful UPLOAD/DOWNLOAD; LOGIN records, no canary passwords, live `docker logs --follow`, logs retained across stop/restart, json-file and local drivers |
| [#21](https://github.com/delfer/docker-alpine-ftp-server/issues/21), [#31](https://github.com/delfer/docker-alpine-ftp-server/issues/31), [#42](https://github.com/delfer/docker-alpine-ftp-server/pull/42), commit `9fd6e07`: groups | Existing six account permutations also verify the auto user retains its own primary group, plus GID-only/new-group cases; real multiuser login/transfer and numeric file ownership; two users sharing existing www-data GID82 can read each other's group-readable files |
| [#70](https://github.com/delfer/docker-alpine-ftp-server/pull/70): private homes | Existing FS-003 checks new homes0750. `existing-homes-and-volume-recreate` preserves administrator modes0700/0750/2770 and unrelated nested UID/GID/mode/bytes across fresh containers on one named volume. `symlink-home-mode` checks the target's0700 rather than restoring the symlink's0777 |
| [#8](https://github.com/delfer/docker-alpine-ftp-server/issues/8), [#38](https://github.com/delfer/docker-alpine-ftp-server/issues/38): account/custom-home restart | `custom-home-restart`: `/home/alice/nested`, UID10000/GID82, login, persistent bytes and two restarts. A pre-existing custom-home account's existing nonfatal adduser warning must not become fatal through a blanket `set -e` |
| [#23](https://github.com/delfer/docker-alpine-ftp-server/issues/23), [#24](https://github.com/delfer/docker-alpine-ftp-server/pull/24): reverted default chroot | Existing `test_FS_006_default_no_chroot` remains enabled; the product config and default chroot policy are unchanged |
| [#40](https://github.com/delfer/docker-alpine-ftp-server/pull/40), [#52](https://github.com/delfer/docker-alpine-ftp-server/issues/52), [#62](https://github.com/delfer/docker-alpine-ftp-server/pull/62): TLS | All session/stop/worker checks run on plain, TLS1.2 and TLS1.3. Existing certificate/reuse/legacy-protocol rejection tests remain enabled; invalid certificate paths must fail startup rather than leave a ghost or plaintext service |
| [#74](https://github.com/delfer/docker-alpine-ftp-server/pull/74): volume semantics | Dockerfile adds no VOLUME; named-volume recreation explicitly verifies contents and metadata |

`custom-config-and-passive-range` also checks native banner/umask settings and
nondefault MIN_PORT/MAX_PORT. `default-user-and-custom-command` verifies the
published default account and propagation of a custom command's exit code7.
`invalid-home-is-not-modified` rejects file/dangling-link homes before inode
mode, owner or contents can be changed. `nonroot-config-rejected` verifies that fixing config ownership in the fixture
does not bypass vsftpd's root-ownership security check.

## Negative controls

The same assertion functions are tested against deliberately broken fixtures:

- `control/direct-foreground-pid1`: override the entrypoint to run foreground as
  PID1; the normal SIGTERM stop assertion must detect fallback SIGKILL.
- `control/disabled-audit`: real transfers succeed with xferlog disabled; the
  normal audit assertion must reject missing records.
- `control/worker-pidfile`: keep a real bob worker alive and temporarily point the
  pidfile at it; the normal socket-ownership assertion must reject that PID.

Only the precise expected assertion is accepted for these controls. Setup,
protocol, or unrelated errors still fail the control. Production-image failures
are never xfailed, skipped, retried, or converted to passing records.

## Running

```sh
python3 tests/run.py --image ftp-under-test:local
python3 tests/run.py --image ftp-under-test:local --suite regressions
python3 tests/run.py --image ftp-under-test:local --suite accounts
python3 tests/run.py --image ftp-under-test:local --suite regressions --startup-attempts 50
```

The default `all` includes the existing protocol/account tests and these new
regressions/controls. `--suite protocols` runs only the existing client protocol
profiles. Suite selection is for focused local diagnosis; CI uses the default.

The initially unavailable port/DNS may be polled before the first greeting;
EOF, authentication failures and TLS errors after connect are not retried.
Separate early-start containers are independent test attempts, not retries of a
failed assertion. RPC/barrier/socket timeouts and stop/kill deadlines are bounded.
A stopped upload is expected to be interrupted, not silently marked completed.

This does not claim the full research catalogue, router/FXP, ARM execution, old
kernels, or every Docker logging driver. The Dockerfile, log destination,
background/tini/pidproxy design and upstream dependency versions are preserved.

Killed-worker closure is checked by reading terminal replies to actual EOF/reset
within a deadline, without sending another command. Fatal diagnostics may be
interleaved or repeat their prefixes; their wording is not an API contract. A
timeout or an ordinary reply still fails, and the other users must transfer
correct bytes. Received terminal diagnostics are retained in client artifacts.
