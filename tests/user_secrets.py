"""USERS_FILE failures, literal credentials and projected read-only volumes."""
import uuid

from configuration import snapshot
from regressions import Client, listener_pid, stop

SECRET = '/run/secrets/ftp users'
PASSWORD = r'pa\ss*?[x]&;=$()`'
CREDENTIALS = dict(alice=PASSWORD, bob='-n', charlie=r'-e\n', globber='*')
SPEC = ' '.join(name+'|'+password for name, password in CREDENTIALS.items())


def rejected_files(h):
    # Reuse a live fixture so failure must preserve pre-existing accounts and
    # cannot quietly reach either a custom command or the daemon.
    entries = [
        ('tmp/secret-empty', b'', 0o400, 0, 0),
        ('tmp/secret-spaces', b' \t\n\n', 0o400, 0, 0),
        ('tmp/secret-private', b'alice|test-pass-a', 0o400, 0, 0),
        ('tmp/secret-directory', None, 0o755, 0, 0),
        ('tmp/secret-broken-link', '/tmp/secret-missing', 0o777, 0, 0),
        ('tmp/secret-bin', None, 0o755, 0, 0),
        ('tmp/secret-bin/cat', b'#!/bin/sh\nprintf partial-secret\nexit 73\n', 0o755, 0, 0),
    ]
    with h.Server(files=entries, command=('sleep', '3600'), startup_wait=0) as server:
        server.exec('mkfifo', '/tmp/secret-fifo')
        before = tuple(snapshot(server, p) for p in ('/etc/passwd', '/etc/group', '/etc/shadow'))
        for label, environment, user, diagnostic in [
            ('missing', ('USERS_FILE=/tmp/secret-missing',), '0', 'readable regular file'),
            ('empty-path', ('USERS_FILE=',), '0', 'readable regular file'),
            ('directory', ('USERS_FILE=/tmp/secret-directory',), '0', 'readable regular file'),
            ('fifo', ('USERS_FILE=/tmp/secret-fifo',), '0', 'readable regular file'),
            ('broken-link', ('USERS_FILE=/tmp/secret-broken-link',), '0', 'readable regular file'),
            ('unreadable', ('USERS_FILE=/tmp/secret-private',), '65534', 'readable regular file'),
            ('read-error', ('USERS_FILE=/tmp/secret-private', 'PATH=/tmp/secret-bin:/bin:/usr/bin'),
             '0', 'readable regular file'),
            ('empty', ('USERS_FILE=/tmp/secret-empty',), '0', 'at least one user'),
            ('whitespace', ('USERS_FILE=/tmp/secret-spaces',), '0', 'at least one user'),
            ('conflict', ('USERS_FILE=/tmp/secret-private', 'USERS=alice|test-pass-a'),
             '0', 'mutually exclusive'),
            ('empty-conflict', ('USERS_FILE=/tmp/secret-private', 'USERS='),
             '0', 'mutually exclusive'),
        ]:
            def verify(environment=environment, user=user, diagnostic=diagnostic):
                args = ['exec', '--user', user]
                for item in environment:
                    args += ['-e', item]
                result = h.docker(*args, server.name, 'env', '-u', 'USERS',
                                  # Restore only an explicitly supplied USERS.
                                  *[item for item in environment if item.startswith('USERS=')],
                                  '/bin/start_vsftpd.sh', 'touch', '/tmp/secret-command-ran',
                                  check=False, timeout=10)
                h.require(result.returncode != 0, 'Invalid secret was accepted')
                h.require(diagnostic in result.stderr, 'Missing secret diagnostic')
                h.require(not result.stdout, 'Secret loader printed data')
                h.require('partial-secret' not in result.stderr and 'test-pass-a' not in result.stderr,
                          'Secret loader leaked credentials')
                h.require(tuple(snapshot(server, p) for p in ('/etc/passwd', '/etc/group', '/etc/shadow'))
                          == before, 'Rejected secret changed accounts')
                h.require(h.docker('exec', server.name, 'test', '!', '-e', '/tmp/secret-command-ran',
                                   check=False).returncode == 0, 'Rejected secret ran the custom command')
            h.check('secrets/reject/'+label, verify)


def literal_logins(h, security, ending):
    data = ((SPEC.replace(' ', '\n') if security == 'tls13' else SPEC)+ending).encode()
    files = [(SECRET[1:], data, 0o400, 0, 0), ('globber|expanded', b'', 0o600, 0, 0)]
    with h.Server(users=None, security=security, files=files,
                  extra_env=('USERS_FILE='+SECRET,)) as server:
        before = snapshot(server, SECRET)
        with Client(h, server, credentials=CREDENTIALS) as client:
            client.call('persistent')
            client.call('login_denied', user='alpineftp', password='alpineftp')
            stop(h, server)
            server.start()
            client.call('persistent', verify=True)
        h.require(snapshot(server, SECRET) == before, 'Startup or restart modified secret')
        h.require(h.docker('exec', server.name, 'id', 'alpineftp', check=False).returncode != 0,
                  'Secret login also enabled the default account')
        environment = server.exec('cat', f'/proc/{listener_pid(h, server)}/environ').stdout
        for password in CREDENTIALS.values():
            h.require(password not in server.logs(), 'Credentials leaked to server logs')
            h.require(password not in environment, 'File credentials exported to daemon')


def legacy_default(h, users):
    with h.Server(users=users, extra_env=('UNRELATED=ignored\nUSERS=bogus|bogus\nUSERS_FILE=/missing',)) as server:
        with Client(h, server, credentials=dict(alpineftp='alpineftp')) as client:
            client.call('persistent')


def invalid_account(h, spec):
    with h.Server(users=None, files=[(SECRET[1:], spec.encode(), 0o400, 0, 0)],
                  extra_env=('USERS_FILE='+SECRET,), autostart=False, startup_wait=0,
                  command=('sh', '-c', 'echo custom-command-ran')) as server:
        server.start()
        status = int(h.docker('wait', server.name, timeout=10).stdout.strip())
        h.require(status != 0, 'Invalid secret account did not stop startup')
        h.require('custom-command-ran' not in server.logs(), 'Invalid account reached custom command')
        h.require('test-pass-a' not in server.logs(), 'Invalid account leaked password')


def projected_volumes(h):
    # Model Kubernetes' ..data replacement on a writable backing volume while
    # the application sees both the Secret and ConfigMap directories read-only.
    volume = 'ftp-secrets-'+uuid.uuid4().hex
    h.docker('volume', 'create', volume)
    try:
        with h.Server(extra_args=('--mount', 'type=volume,src='+volume+',dst=/projected'),
                      command=('sleep', '3600'), startup_wait=0) as seed:
            entries = []
            for directory in ('secret', 'config'):
                for generation in ('v1', 'v2'):
                    entries.append((f'projected/{directory}/{generation}', None, 0o755, 0, 0))
                entries.append((f'projected/{directory}/..data', 'v1', 0o777, 0, 0))
            for generation, password, banner in [('v1', 'test-pass-a', 'First config'),
                                                  ('v2', 'test-pass-b', 'Second config')]:
                config = (h.ROOT/'vsftpd.conf').read_text()
                config = '\n'.join(line for line in config.splitlines()
                                   if not line.startswith('ftpd_banner='))
                entries += [
                    (f'projected/secret/{generation}/users',
                     f'alice|{password}|/home/alice/nested|10000|82\n'.encode(),
                     0o400, 0, 0),
                    (f'projected/config/{generation}/vsftpd.conf',
                     (config+'\nftpd_banner='+banner+'\n').encode(), 0o444, 0, 0),
                ]
            entries += [('projected/secret/users', '..data/users', 0o777, 0, 0),
                        ('projected/config/vsftpd.conf', '..data/vsftpd.conf', 0o777, 0, 0)]
            h.copy_files(seed.name, entries)
            before = [snapshot(seed, f'/projected/{d}/{v}/{f}')
                      for d, f in [('secret', 'users'), ('config', 'vsftpd.conf')]
                      for v in ('v1', 'v2')]
            path = h.docker('volume', 'inspect', '--format', '{{.Mountpoint}}', volume).stdout.strip()
            mounts = tuple(arg for directory, destination in [('secret', '/run/secrets'),
                                                              ('config', '/etc/vsftpd')]
                           for arg in ('--mount', f'type=bind,src={path}/{directory},dst={destination},readonly'))
            with h.Server(users=None, extra_args=mounts,
                          extra_env=('USERS_FILE=/run/secrets/users', 'CONF_local_umask=077')) as server:
                for generation, password, banner in [('v1', 'test-pass-a', 'First config'),
                                                      ('v2', 'test-pass-b', 'Second config')]:
                    if generation == 'v2':
                        for directory in ('secret', 'config'):
                            seed.exec('sh', '-c', 'cd "$1" && ln -s v2 ..next && mv -Tf ..next ..data',
                                      'sh', '/projected/'+directory)
                        stop(h, server)
                        server.start()
                    with Client(h, server, credentials=dict(alice=password),
                                homes=dict(alice='/home/alice/nested')) as client:
                        client.call('persistent')
                        if generation == 'v2':
                            client.call('login_denied', user='alice', password='test-pass-a')
                    h.require(banner in server.exec('cat', '/var/run/vsftpd/vsftpd.conf').stdout,
                              'Projected ConfigMap was not reread')
                    h.require(server.exec('id', '-u', 'alice').stdout.strip() == '10000', 'Secret UID ignored')
                    h.require(server.exec('id', '-g', 'alice').stdout.strip() == '82', 'Secret GID ignored')
                    h.require(before == [snapshot(seed, f'/projected/{d}/{v}/{f}')
                                         for d, f in [('secret', 'users'), ('config', 'vsftpd.conf')]
                                         for v in ('v1', 'v2')],
                              'Application modified projected sources')
    finally:
        h.docker('volume', 'rm', volume, check=False)


def run(h):
    h.check('secrets/rejection-fixture', lambda: rejected_files(h))
    for security, ending in [('plain', ''), ('tls12', '\n'), ('tls13', '\n\n')]:
        h.check('secrets/literal-logins/'+security, lambda s=security, e=ending: literal_logins(h, s, e))
    for label, users in [('unset', None), ('empty', '')]:
        h.check('secrets/legacy-default/'+label, lambda u=users: legacy_default(h, u))
    for label, spec in [('existing-user', 'root|test-pass-a'),
                        ('root-home', 'root|test-pass-a|/root'),
                        ('invalid-uid', 'alice|test-pass-a||not-a-uid'),
                        ('invalid-gid', 'alice|test-pass-a|||not-a-gid')]:
        h.check('secrets/invalid-account/'+label, lambda s=spec: invalid_account(h, s))
    h.check('secrets/projected-volumes', lambda: projected_volumes(h))
