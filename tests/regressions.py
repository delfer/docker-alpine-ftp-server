"""Behavioral regressions for the histories documented in REGRESSIONS.md."""
import collections
import contextlib
import json
import selectors
import subprocess
import time
import uuid

CREDENTIALS = dict(alice='test-pass-a', bob='test-pass-b', charlie='test-pass-c')
USERS = 'alice|test-pass-a bob|test-pass-b||10000|12000 charlie|test-pass-c||10001|82'


class Client:
    """Keep independent FTP sessions alive while the host stops/restarts vsftpd."""
    def __init__(self, harness, server, credentials=None, homes=None):
        self.h, self.server = harness, server
        self.credentials = credentials or CREDENTIALS
        self.scenario = dict(credentials=self.credentials, homes=homes or {})
        self.name = server.name+'-sessions'
        self.process = self.stderr = None
        self.events = []
        self.terminal_replies = []

    def __enter__(self):
        h = self.h
        try:
            h.docker('create', '--name', self.name, '--network', self.server.name,
                     '-e', 'TEST_SECURITY='+self.server.security,
                     '-e', 'TEST_SCENARIO='+json.dumps(self.scenario),
                     h.ARGS.client_image, 'sleep', '3600')
            h.docker('cp', str(h.ROOT/'tests')+'/.', self.name+':/tests')
            h.docker('cp', str(h.ARGS.certs)+'/.', self.name+':/certs')
            h.docker('start', self.name)
            self.stderr = (h.ARGS.output/(self.name+'.log')).open('w')
            self.process = subprocess.Popen(
                h.DOCKER+['exec', '-i', self.name, 'python', '-u', '/tests/session_client.py'],
                env=h.ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                text=True, bufsize=1)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def call(self, op, **args):
        self.process.stdin.write(json.dumps(dict(op=op, **args))+'\n')
        self.process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            self.h.require(selector.select(60), 'Session client timed out during '+op)
        line = self.process.stdout.readline()
        self.h.require(line, 'Session client exited during '+op+'; see '+self.name+'.log')
        result = json.loads(line)
        self.h.require(result.get('ok'), result.get('detail', str(result)))
        self.events.extend(result.get('events', []))
        self.terminal_replies.extend(result.get('terminal_replies', []))
        return result

    def __exit__(self, *exc):
        try:
            (self.h.ARGS.output/(self.name+'.json')).write_text(json.dumps(
                dict(server=self.server.name, security=self.server.security,
                     expected_transfer_events=self.events,
                     terminal_replies=self.terminal_replies), indent=2))
        finally:
            if self.process:
                # Terminate the exec client before removing its container, even
                # when a protocol assertion or startup fails.
                self.process.terminate()
                try:
                    self.process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.communicate()
            self.h.docker('rm', '-f', self.name, check=False)
            if self.stderr:
                self.stderr.close()


def listener_pid(h, server):
    """Verify pidfile against the owner of TCP21, including with workers alive."""
    deadline = time.monotonic()+2
    while True:
        probe = h.docker('exec', server.name, 'cat', '/var/run/vsftpd/vsftpd.pid', check=False)
        if probe.returncode == 0:
            break
        h.require(server.state()['Running'], 'Server exited before writing pidfile: '+server.logs())
        h.require(time.monotonic() < deadline, 'Listener pidfile was never written')
        time.sleep(.02)
    pid = int(probe.stdout.strip())
    sockets = server.exec('netstat', '-ltnp').stdout
    owners = [line.split()[-1].split('/')[0] for line in sockets.splitlines()
              if len(line.split()) >= 7 and line.split()[3].endswith(':21')
              and line.split()[5] == 'LISTEN']
    h.require(owners == [str(pid)], f'pidfile {pid} does not own TCP21: {sockets}')
    tree = server.exec('ps', '-o', 'pid,ppid,pgid,sid,stat,user,comm,args').stdout
    (h.ARGS.output/(server.name+'-processes.log')).write_text(tree+'\n'+sockets)
    return pid


def verify_logs(h, server, client, live=None):
    log = server.logs()
    expected = collections.Counter((e['user'], e['file'], e['operation']) for e in client.events)
    for (user, name, operation), count in expected.items():
        matches = [line for line in log.splitlines()
                   if '['+user+'] OK '+operation+':' in line and name in line]
        h.require(len(matches) == count, f'Audit mismatch for {(user, name, operation)}: {len(matches)} != {count}')
    for user, password in client.credentials.items():
        h.require('['+user+'] OK LOGIN:' in log, 'Missing login log for '+user)
        h.require(password not in log, 'Password leaked to server logs')
    if live is not None:
        text = live.read_text()
        h.require('OK UPLOAD:' in text and 'OK DOWNLOAD:' in text, 'Live docker logs lost transfers')


@contextlib.contextmanager
def follow_logs(h, server):
    path = h.ARGS.output/(server.name+'-follow.log')
    with path.open('w') as output:
        process = subprocess.Popen(h.DOCKER+['logs', '--follow', server.name],
                                   env=h.ENV, stdout=output, stderr=subprocess.STDOUT)
        try:
            yield path
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def open_users(client):
    for user in client.credentials:
        client.call('open', id=user, user=user)


def assert_owners(h, server, credentials):
    for user in credentials:
        owner = server.exec('id', '-u', user).stdout.strip()
        group = server.exec('id', '-g', user).stdout.strip()
        actual = server.exec('stat', '-c', '%u:%g', '/ftp/'+user+'/persist-'+user+'.bin').stdout.strip()
        h.require(actual == owner+':'+group, 'Wrong uploaded file owner for '+user+': '+actual)


def sessions_and_logs(h, security, driver='json-file'):
    with h.Server(users=USERS, security=security, extra_args=('--log-driver', driver)) as server:
        with Client(h, server) as client, follow_logs(h, server) as live:
            client.call('ready')  # First QUIT must not terminate the listener (#15).
            pid = listener_pid(h, server)
            client.call('persistent')
            assert_owners(h, server, client.credentials)
            client.call('parallel')  # 3 users x 4 data modes; exact byte equality.
            open_users(client)
            client.call('churn')
            client.call('close', id='bob')
            for user in ('alice', 'charlie'):
                client.call('transfer', id=user)
            client.call('open', id='bob', user='bob')
            client.call('transfer', id='bob')
            h.require(listener_pid(h, server) == pid, 'Listener changed after client disconnect')
            for user in client.credentials:
                client.call('close', id=user)
            deadline = time.monotonic()+2
            while True:
                tree = server.exec('ps', '-o', 'stat,comm').stdout
                if not any(line.split()[0].startswith('Z') for line in tree.splitlines()[1:]):
                    break
                h.require(time.monotonic() < deadline, 'Unreaped workers: '+tree)
                time.sleep(.02)
            verify_logs(h, server, client, live)


def worker_death(h, security):
    with h.Server(users=USERS, security=security) as server, Client(h, server) as client:
        client.call('ready')
        pid = listener_pid(h, server)
        open_users(client)
        rows = server.exec('ps', '-o', 'pid,user,comm').stdout.splitlines()[1:]
        workers = [line.split()[0] for line in rows if line.split()[1:] == ['bob', 'vsftpd']]
        h.require(workers, 'No bob worker exists to kill')
        server.exec('kill', '-KILL', workers[0])
        client.call('broken', ids=['bob'])
        for user in ('alice', 'charlie'):
            client.call('transfer', id=user)
        client.call('open', id='bob', user='bob')
        client.call('transfer', id='bob')
        h.require(listener_pid(h, server) == pid, 'One user killed the listener')
        verify_logs(h, server, client)


def stop(h, server):
    started = time.monotonic()
    h.docker('stop', '--time', '3', server.name, timeout=8)
    state = server.state()
    h.require(not state['Running'] and state['ExitCode'] != 137,
              'Stop required SIGKILL instead of handling SIGTERM: '+str(state))
    h.require(time.monotonic()-started < 5, 'Stop exceeded bounded shutdown budget')


def stop_restart(h, security, homes=None, users=USERS, credentials=None):
    with h.Server(users=users, security=security) as server:
        with Client(h, server, credentials, homes) as client:
            client.call('ready')
            client.call('persistent')
            stop(h, server)
            server.start()
            client.call('ready')
            client.call('persistent', verify=True)
            open_users(client)
            uploads = [client.call('begin_upload', id=user) for user in client.credentials]
            for upload in uploads:
                home = (homes or {}).get(upload['user'], '/ftp/'+upload['user'])
                size = int(server.exec('stat', '-c', '%s', home+'/'+upload['file']).stdout)
                h.require(size > 0, 'Upload never wrote data before stop')
            stop(h, server)
            client.call('broken', ids=list(client.credentials))
            server.start()
            client.call('ready')
            client.call('persistent', verify=True)
            verify_logs(h, server, client)


def listener_death(h, security):
    with h.Server(users=USERS, security=security) as server, Client(h, server) as client:
        client.call('ready')
        open_users(client)
        pid = listener_pid(h, server)
        # The exec command may itself be terminated when the namespace exits.
        h.docker('exec', server.name, 'kill', '-KILL', str(pid), check=False)
        deadline = time.monotonic()+5
        while server.state()['Running'] and time.monotonic() < deadline:
            time.sleep(.02)
        h.require(not server.state()['Running'], 'Container survived without TCP listener')
        client.call('broken', ids=list(client.credentials))


def early_start(h, security):
    # Client container and Python process exist before the daemon starts, so
    # the first connection is not delayed by docker cp/create or an exec probe.
    with h.Server(security=security, startup_wait=0, autostart=False) as server:
        with Client(h, server, dict(alice='test-pass-a')) as client:
            server.start()
            client.call('ready')
            pid = listener_pid(h, server)
            for _ in range(3):
                client.call('open', id='alice', user='alice')
                client.call('transfer', id='alice')
                client.call('close', id='alice', abrupt=True)
            h.require(listener_pid(h, server) == pid, 'Early disconnect changed listener')
            verify_logs(h, server, client)


def existing_homes(h):
    volume = 'ftp-test-homes-'+uuid.uuid4().hex
    h.docker('volume', 'create', volume)
    mounts = ('--mount', 'type=volume,src='+volume+',dst=/ftp')
    users = 'alice|test-pass-a||10000|12000 bob|test-pass-b||10001|82 charlie|test-pass-c||10002|12002'
    modes = dict(alice=0o700, bob=0o750, charlie=0o2770)
    files = [('ftp/'+u, None, m, 0, 0) for u, m in modes.items()]
    files += [('ftp/'+u+'/nested', None, 0o711, 12345, 23456) for u in modes]
    files += [('ftp/'+u+'/nested/canary', b'unchanged\x00data', 0o640, 12345, 23456) for u in modes]
    try:
        for iteration in range(2):
            with h.Server(users=users, extra_args=mounts, files=files if iteration == 0 else ()) as server:
                for user, mode in modes.items():
                    actual = server.exec('stat', '-c', '%a', '/ftp/'+user).stdout.strip()
                    h.require(int(actual, 8) == mode, f'Existing {user} mode changed: {actual}')
                    nested = server.exec('stat', '-c', '%u:%g:%a', '/ftp/'+user+'/nested/canary').stdout.strip()
                    h.require(nested == '12345:23456:640', 'Nested metadata changed: '+nested)
                    data = server.exec('od', '-An', '-tx1', '/ftp/'+user+'/nested/canary').stdout.split()
                    h.require(bytes(int(x, 16) for x in data) == b'unchanged\x00data', 'Mounted file changed')
    finally:
        h.docker('volume', 'rm', volume, check=False)


def symlink_home(h):
    files = [('data', None, 0o755, 0, 0), ('data/alice', None, 0o700, 0, 0),
             ('ftp', None, 0o755, 0, 0), ('ftp/alice', '/data/alice', 0o777, 0, 0)]
    with h.Server(users='alice|test-pass-a||10000|82', files=files) as server:
        actual = server.exec('stat', '-L', '-c', '%a:%u:%g', '/ftp/alice').stdout.strip()
        h.require(actual == '700:10000:82', 'Symlink target permissions changed: '+actual)


def shared_group(h):
    users = 'alice|test-pass-a||10000|82 bob|test-pass-b||10001|82'
    with h.Server(users=users) as server, Client(h, server, dict(alice='test-pass-a', bob='test-pass-b')) as client:
        client.call('ready')
        client.call('persistent', private=False)
        assert_owners(h, server, client.credentials)
        client.call('read_peer', user='bob', owner='alice')
        client.call('read_peer', user='alice', owner='bob')
        verify_logs(h, server, client)


def custom_config(h):
    config = (h.ROOT/'vsftpd.conf').read_text().replace('local_umask=022', 'local_umask=077')
    config = '\n'.join(line for line in config.splitlines() if not line.startswith('ftpd_banner='))
    config += '\nftpd_banner=Regression custom banner\n'
    with h.Server(config=config, extra_env=('MIN_PORT=22220', 'MAX_PORT=22230')) as server:
        with Client(h, server, dict(alice='test-pass-a')) as client:
            client.call('ready')
            client.call('config', banner='Regression custom banner', min_port=22220, max_port=22230)
            mode = server.exec('stat', '-c', '%a', '/ftp/alice/custom-config.bin').stdout.strip()
            h.require(mode == '600', 'Custom umask ignored: '+mode)
            verify_logs(h, server, client)


def custom_command(h):
    name = 'ftp-test-command-'+uuid.uuid4().hex
    try:
        h.docker('create', '--name', name, h.ARGS.image, 'sh', '-c',
                 'test "$(id -un alpineftp)" = alpineftp && test "$(stat -c %a /ftp/alpineftp)" = 750 && exit 7')
        h.docker('start', name)
        status = int(h.docker('wait', name).stdout.strip())
        h.require(status == 7, 'Default user/custom command exit status regressed: '+str(status))
    finally:
        h.docker('rm', '-f', name, check=False)



def rejects(h, function, message):
    """A negative control must fail for its intended reason, not fixture errors."""
    try:
        function()
    except AssertionError as error:
        h.require(message in str(error), 'Negative control failed for another reason: '+str(error))
    else:
        raise AssertionError('Regression assertion accepted a deliberately broken control')


def direct_pid1_control(h):
    # Recreate the historical direct foreground entrypoint without changing the
    # product image. This control checks actual SIGTERM behavior, not a config
    # string, so it does not invent a prohibition on foreground under tini.
    with h.Server(extra_args=('--init=false', '--entrypoint', '/bin/start_vsftpd.sh'),
                  command=('sh', '-c', 'exec vsftpd /etc/vsftpd/vsftpd.conf -obackground=NO')) as server:
        h.require(server.exec('cat', '/proc/1/comm').stdout.strip() == 'vsftpd',
                  'Direct PID1 control was not constructed correctly')
        rejects(h, lambda: stop(h, server), 'Stop required SIGKILL')


def no_logging_control(h):
    config = (h.ROOT/'vsftpd.conf').read_text().replace('xferlog_enable=YES', 'xferlog_enable=NO')
    with h.Server(users=USERS, config=config) as server, Client(h, server) as client:
        client.call('ready')
        client.call('persistent')  # Transfers really succeed while audit is absent.
        rejects(h, lambda: verify_logs(h, server, client), 'Audit mismatch')


def worker_pid_control(h):
    with h.Server(users=USERS) as server, Client(h, server) as client:
        client.call('ready')
        original = listener_pid(h, server)
        client.call('open', id='bob', user='bob')
        rows = server.exec('ps', '-o', 'pid,user,comm').stdout.splitlines()[1:]
        workers = [line.split()[0] for line in rows if line.split()[1:] == ['bob', 'vsftpd']]
        h.require(workers, 'Worker PID control has no live worker')
        try:
            server.exec('sh', '-c', 'printf "%s\\n" "$1" > /var/run/vsftpd/vsftpd.pid', 'sh', workers[0])
            rejects(h, lambda: listener_pid(h, server), 'does not own TCP21')
        finally:
            server.exec('sh', '-c', 'printf "%s\\n" "$1" > /var/run/vsftpd/vsftpd.pid', 'sh', str(original))


def nonroot_config(h):
    config = (h.ROOT/'vsftpd.conf').read_bytes()
    with h.Server(files=[('etc/vsftpd/vsftpd.conf', config, 0o600, 1000, 1000)],
                  startup_wait=0, autostart=False) as server:
        server.start()
        deadline = time.monotonic()+3
        while server.state()['Running'] and time.monotonic() < deadline:
            time.sleep(.02)
        state = server.state()
        h.require(not state['Running'] and state['ExitCode'] != 0,
                  'Non-root config did not fail startup: '+str(state))


def invalid_tls(h):
    with h.Server(extra_env=('TLS_CERT=/missing-cert', 'TLS_KEY=/missing-key'),
                  startup_wait=0, autostart=False) as server:
        server.start()
        deadline = time.monotonic()+3
        while server.state()['Running'] and time.monotonic() < deadline:
            time.sleep(.02)
        state = server.state()
        h.require(not state['Running'] and state['ExitCode'] != 0,
                  'Invalid TLS left a live/nominally successful container: '+str(state))


def invalid_home(h):
    # No chmod/chown is allowed to touch a regular file or dangling symlink
    # supplied as a home. Inspect the stopped container's tar metadata as well
    # as its exit status; a late error after modifying it would be insufficient.
    import io
    import tarfile
    for data in (b'unchanged file bytes', '/missing-target'):
        mode = 0o640 if isinstance(data, bytes) else 0o777
        with h.Server(users='alice|test-pass-a|/home-marker|10000|82',
                      files=[('home-marker', data, mode, 12345, 23456)],
                      startup_wait=0, autostart=False) as server:
            server.start()
            deadline = time.monotonic()+3
            while server.state()['Running'] and time.monotonic() < deadline:
                time.sleep(.02)
            state = server.state()
            h.require(not state['Running'] and state['ExitCode'] != 0,
                      'Invalid home did not fail startup: '+str(state))
            result = subprocess.run(h.DOCKER+['cp', '-a', server.name+':/home-marker', '-'],
                                    env=h.ENV, capture_output=True, check=True, timeout=30)
            with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
                entry = tar.getmembers()[0]
                h.require((entry.mode, entry.uid, entry.gid) == (mode, 12345, 23456),
                          'Rejected home metadata was modified')
                if isinstance(data, bytes):
                    h.require(tar.extractfile(entry).read() == data, 'Rejected home bytes changed')
                else:
                    h.require(entry.issym() and entry.linkname == data, 'Rejected symlink changed')

def run(h):
    for security in ('plain', 'tls12', 'tls13'):
        for label, function in [('disconnects-and-logs', sessions_and_logs),
                                ('worker-death', worker_death), ('stop-restart', stop_restart),
                                ('listener-death', listener_death)]:
            h.check('regression/'+security+'/'+label, lambda f=function, s=security: f(h, s))
        for attempt in range(h.ARGS.startup_attempts):
            h.check(f'regression/{security}/early-start-{attempt}', lambda s=security: early_start(h, s))
    h.check('regression/local-log-driver', lambda: sessions_and_logs(h, 'plain', 'local'))
    for label, function in [('existing-homes-and-volume-recreate', existing_homes),
                            ('symlink-home-mode', symlink_home), ('existing-shared-gid', shared_group),
                            ('custom-config-and-passive-range', custom_config),
                            ('default-user-and-custom-command', custom_command),
                            ('nonroot-config-rejected', nonroot_config),
                            ('invalid-tls-fails-startup', invalid_tls),
                            ('invalid-home-is-not-modified', invalid_home)]:
        h.check('compatibility/'+label, lambda f=function: f(h))
    for label, function in [('direct-foreground-pid1', direct_pid1_control),
                            ('disabled-audit', no_logging_control), ('worker-pidfile', worker_pid_control)]:
        h.check('control/'+label, lambda f=function: f(h))
    h.check('compatibility/custom-home-restart', lambda: stop_restart(
        h, 'plain', dict(alice='/home/alice/nested'),
        'alice|test-pass-a|/home/alice/nested|10000|82', dict(alice='test-pass-a')))
