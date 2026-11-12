# Compatibility review of the entrypoint fixes

The regression/source map is in [tests/REGRESSIONS.md](../../tests/REGRESSIONS.md).
The review focused on the changed entrypoint behavior and relevant historical
fixes, rather than treating every closed issue as proven fixed.

| Change | Regression risk found during review | Final behavior and evidence |
| --- | --- | --- |
| Reset UID_OPT/GROUP_OPT for each user | A duplicate-UID failure can hide a separate leaked primary group | Six account orders assert IDs and the automatic account's own primary group. A mutant that clears only UID_OPT is rejected specifically for the inherited group |
| Resolve GID independently of UID | Breaking the existing-group reuse from `9fd6e07` / #42, or removing group sharing | Existing GID82 is reused; GID-only82/new12000 cases work. Real shared-group users can read group-readable peer files; uploaded numeric owners/groups are checked |
| Private new homes (#70) | Unconditional chmod0750 widens an administrator's0700; BusyBox adduser itself changes existing directory modes | Snapshot existing modes before adduser and restore them; new directories get0750. Named-volume tests preserve0700/0750/2770, nested UID/GID/modes/bytes and data across container recreation |
| Symlink homes | Reading the symlink's0777 then chmodding its target would widen target permissions | Use stat -L consistently with directory/chown/chmod behavior; preserve a symlink target's0700 |
| Invalid home paths | A new chmod could modify an existing regular file configured as a home | Reject regular files and dangling symlinks before account creation/ownership/mode changes. Tests inspect the stopped container's original inode metadata and bytes |
| Startup supervision (#15/#36/#48) | Changing foreground/init/logging/exit-code behavior while repairing PID selection | Keep background, tini, pidproxy and its version. Match the oldest exact vsftpd process; compare pidfile with TCP21's owner while workers exist. Fail on launch/lookup/pidfile errors |
| Root-owned read-only fixtures | Making tests green by disabling vsftpd's config ownership check | Copy explicit root UID/GID and0600 metadata. A deliberately non-root config must still reject startup |

## Historical behavior retained

- Custom-home restart (#38) still permits the existing nonfatal `adduser: user
  in use` warning. A blanket `set -e` was deliberately avoided; the startup
  guards apply to daemon launch/PID handling and invalid home paths. Tests cover
  repeated login and persistent data with the same custom home/credentials.
- Default no-chroot behavior remains after #23/#24. Native vsftpd.conf, absolute
  home paths, TLS policy, stdout destination and custom config settings are
  preserved and exercised by existing/new protocol checks.
- Custom command arguments still execute after account initialization and return
  their actual exit status. The default alpineftp account remains available.
- No recursive ownership/mode changes, automatic VOLUME, dependency, StopSignal,
  architecture list or Dockerfile changes were introduced.

## Scope of the foreground evidence

The tests assert real session, audit and shutdown behavior, not that foreground
is universally forbidden. The direct-PID1 negative control forces `--init=false`
so daemon-wide Docker defaults cannot silently add an init process. It must be
rejected by the normal SIGTERM test because current vsftpd needs SIGKILL in that
configuration. Foreground under tini passed the earlier comparison; that does
not invalidate the historical direct-entrypoint problems or require changing
the supported background design to repair PID selection.

## Verification and bounds

The complete candidate run passed 479 result records; these include client cases,
subtests and suite summaries, not 479 independent catalogue specifications.
Negative controls also rejected disabled audit and a worker substituted for the
listener. Separate local controls rejected the earlier unconditional-home-mode
proposal and a primary-group leak independent of UID leakage.

Execution was on Linux/amd64. This is not execution of the full research
catalogue, ARM variants, old kernels or all logging/network drivers. Existing
USERS escaping/validation limitations and reconfiguration of an already existing
custom-home account's password/home are not solved by these changes. The custom
home restart check covers the same configured account and credentials; it is not
a claim of general account reconciliation.
