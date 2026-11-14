"""Startup, restart and mounted-config compatibility for CONF_ overrides."""
import io
import json
import subprocess
import tarfile
import uuid

from configuration import snapshot
from regressions import listener_pid, stop

CONFIG_PATH = '/etc/vsftpd/vsftpd.conf'
BANNER = r'FTP & FTPS / literal = value; | backslash\ test'


def client(h, server, **scenario):
    name = server.name+'-config-client-'+uuid.uuid4().hex
    scenario = dict(banner=BANNER, min_port=22320, max_port=22330, **scenario)
    try:
        h.docker('create', '--name', name, '--network', server.name,
                 '-e', 'TEST_SECURITY='+server.security, '-e', 'TEST_CONFIG='+json.dumps(scenario),
                 h.ARGS.client_image, 'python', '/tests/config_client.py')
        h.docker('cp', str(h.ROOT/'tests')+'/.', name+':/tests')
        h.docker('cp', str(h.ARGS.certs)+'/.', name+':/certs')
        h.docker('start', name)
        status = int(h.docker('wait', name).stdout.strip())
        log = h.docker('logs', name, check=False)
        (h.ARGS.output/(name+'.log')).write_text(log.stdout+log.stderr)
        h.require(status == 0, 'Effective configuration check failed: '+log.stdout+log.stderr)
    finally:
        h.docker('rm', '-f', name, check=False)


def settings(readonly=False):
    return ('CONF_FTPD_BANNER='+BANNER, 'CONF_local_umask=077',
            'MIN_PORT=22220', 'MAX_PORT=22230', 'ADDRESS=must-not-resolve.invalid',
            'CONF_pasv_min_port=22320', 'CONF_PASV_MAX_PORT=22330', 'CONF_pasv_address=ftp.test',
            'CONF_chroot_local_user=YES', 'CONF_allow_writeable_chroot=YES',
            'CONF_write_enable='+('NO' if readonly else 'YES'))


def effective_settings(h, security, readonly):
    # Deliberate duplicates and a commented default ensure overrides are effective,
    # rather than merely appended where later values could silently win.
    config = (h.ROOT/'vsftpd.conf').read_text()+'\nftpd_banner=old duplicate\n# local_umask = 022\n'
    with h.Server(security=security, config=config, extra_env=settings(readonly)) as server:
        if readonly:
            server.exec('sh', '-c', 'printf existing-data > /ftp/alice/existing; chmod 644 /ftp/alice/existing')
        before = snapshot(server, CONFIG_PATH)
        for iteration in range(2):
            client(h, server, chroot=True, readonly=readonly)
            if readonly:
                h.require(server.exec('cat', '/ftp/alice/existing').stdout == 'existing-data',
                          'Read-only policy changed existing bytes')
                h.require(h.docker('exec', server.name, 'test', '!', '-e', '/ftp/alice/new',
                                   check=False).returncode == 0, 'Read-only policy created a file')
            else:
                for method in ('PASV', 'EPSV', 'PORT', 'EPRT'):
                    mode = server.exec('stat', '-c', '%a', '/ftp/alice/config-'+method+'.bin').stdout.strip()
                    h.require(mode == '600', 'CONF_local_umask was ignored: '+mode)
            listener_pid(h, server)
            if iteration == 0:
                stop(h, server)
                server.start()
                h.require(snapshot(server, CONFIG_PATH) == before, 'Restart rewrote the effective config')


def tls_precedence(h):
    # Use the plain fixture profile so it does not replace these deliberately
    # broken legacy TLS paths with its automatic TLS_CERT/TLS_KEY settings.
    environment = settings()+('TLS_CERT=/missing-legacy-cert', 'TLS_KEY=/missing-legacy-key',
                              'CONF_rsa_cert_file=/certs/cert.pem',
                              'CONF_rsa_private_key_file=/certs/key.pem')
    with h.Server(extra_env=environment) as server:
        for security in ('tls12', 'tls13'):
            server.security = security
            client(h, server, chroot=True, reject_plaintext=True)


def stopped_config(h, server):
    result = subprocess.run(h.DOCKER+['cp', '-a', server.name+':'+CONFIG_PATH, '-'],
                            env=h.ENV, capture_output=True, check=True, timeout=30)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        entry = tar.getmembers()[0]
        return tar.extractfile(entry).read(), entry.mode, entry.uid, entry.gid


def rejected_start(h, environment, diagnostic, owner=0):
    original = (h.ROOT/'vsftpd.conf').read_bytes()
    with h.Server(extra_env=environment,
                  files=[('etc/vsftpd/vsftpd.conf', original, 0o640, owner, owner)],
                  autostart=False, startup_wait=0) as server:
        server.start()
        status = int(h.docker('wait', server.name, timeout=10).stdout.strip())
        h.require(status != 0 and not server.state()['Running'], 'Bad config left a live/successful server')
        if diagnostic:
            h.require(diagnostic in server.logs(), 'Missing startup failure: '+server.logs())
        content, mode, uid, gid = stopped_config(h, server)
        h.require((mode, uid, gid) == (0o640, owner, owner), 'Updater changed config permissions/ownership')
        if diagnostic:
            h.require(content == original, 'Rejected overrides changed original config')
        else:
            # Native vsftpd config errors can exit without Docker log output.
            # Assert rejection of the actual rendered assignment, not wording.
            for item in environment:
                name, value = item.split('=', 1)
                expected = (name[5:].lower()+'='+value+'\n').encode()
                h.require(expected in content, 'vsftpd was not given the requested option')


def custom_command(h):
    with h.Server(extra_env=('CONF_=invalid',), command=('sh', '-c', 'exit 7'),
                  autostart=False, startup_wait=0) as server:
        before = stopped_config(h, server)
        server.start()
        status = int(h.docker('wait', server.name, timeout=10).stdout.strip())
        h.require(status == 7, 'Updater intercepted custom command exit status')
        h.require(stopped_config(h, server) == before, 'Custom command applied overrides')
        h.require('update_conf:' not in server.logs(), 'Custom command ran updater')


def mounted_configs(h):
    # The bind source lives on the daemon, so these fixtures work remotely too.
    volume = 'ftp-config-'+uuid.uuid4().hex
    h.docker('volume', 'create', volume)
    try:
        with h.Server(extra_args=('--mount', 'type=volume,src='+volume+',dst=/config-source'),
                      command=('sleep', '3600'), startup_wait=0) as seed:
            data = (h.ROOT/'vsftpd.conf').read_bytes()
            h.copy_files(seed.name, [('config-source/vsftpd.conf', data, 0o640, 0, 0)])
            path = h.docker('volume', 'inspect', '--format', '{{.Mountpoint}}', volume).stdout.strip()
            mount = 'type=bind,src='+path+'/vsftpd.conf,dst='+CONFIG_PATH
            before = snapshot(seed, '/config-source/vsftpd.conf')
            with h.Server(extra_args=('--mount', mount), extra_env=settings()) as server:
                client(h, server, chroot=True)
                after = snapshot(seed, '/config-source/vsftpd.conf')
                h.require(after[1].split(':')[:4] == before[1].split(':')[:4],
                          'Bind-mounted config inode/owner/mode changed')
                h.require('ftpd_banner='+BANNER+'\n' in after[0], 'Bind source did not receive overrides')
            # The resulting file also works as a read-only mount without CONF_.
            with h.Server(extra_args=('--mount', mount+',readonly')) as server:
                client(h, server, chroot=True)
            h.require(snapshot(seed, '/config-source/vsftpd.conf') == after,
                      'No-override run wrote a read-only config')
            with h.Server(extra_args=('--mount', mount+',readonly'),
                          extra_env=('CONF_FTPD_BANNER=cannot-write',),
                          autostart=False, startup_wait=0) as server:
                server.start()
                status = int(h.docker('wait', server.name, timeout=10).stdout.strip())
                log = server.logs()
                h.require(status != 0 and ('existing writable file' in log or
                                          'update_conf: failed to write configuration' in log),
                          'Read-only mount override did not fail clearly')
            h.require(snapshot(seed, '/config-source/vsftpd.conf') == after,
                      'Failed read-only override changed bind source')
    finally:
        h.docker('volume', 'rm', volume, check=False)


def run(h):
    for security in ('plain', 'tls12', 'tls13'):
        for readonly in (False, True):
            label = 'readonly' if readonly else 'writable'
            h.check('config/live/'+security+'/'+label,
                    lambda s=security, r=readonly: effective_settings(h, s, r))
    for label, environment, diagnostic, owner in [
        ('invalid-name', ('CONF_=bad',), 'update_conf: invalid CONF_ parameter name', 0),
        ('multiline', ('CONF_ftpd_banner=hello\nwrite_enable=NO',), 'update_conf: multiline value', 0),
        ('conflict', ('CONF_FTPD_BANNER=one', 'CONF_ftpd_banner=two'), 'update_conf: conflicting', 0),
        ('unknown-option', ('CONF_unknown_vsftpd_option=YES',), None, 0),
        ('invalid-boolean', ('CONF_write_enable=not-a-boolean',), None, 0),
        ('nonroot-owner', ('CONF_ftpd_banner=ownership must remain',), None, 1000),
    ]:
        h.check('config/startup-rejects/'+label,
                lambda e=environment, d=diagnostic, o=owner: rejected_start(h, e, d, o))
    h.check('config/custom-command-bypasses-updater', lambda: custom_command(h))
    h.check('config/bind-mounts', lambda: mounted_configs(h))
    h.check('config/tls-path-precedence', lambda: tls_precedence(h))
