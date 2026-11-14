"""CONF_ rendering checks run with the shipped shell, awk and updater."""
def invoke(h, server, path, environment=(), user=None):
    args = ['exec']
    if user is not None:
        args += ['--user', user]
    for item in environment:
        args += ['-e', item]
    return h.docker(*args, server.name, '/bin/update_conf.sh', path, check=False)


def snapshot(server, path):
    return (server.exec('cat', path).stdout,
            server.exec('stat', '-L', '-c', '%i:%u:%g:%a:%y:%z', path).stdout)


def render_case(h, server, source, environment, expected=None, error=None):
    path = '/tmp/config-fixture'
    h.copy_files(server.name, [('tmp/config-fixture', source.encode(), 0o640, 12345, 23456)])
    before = snapshot(server, path)
    result = invoke(h, server, path, environment)
    after = snapshot(server, path)
    if error:
        h.require(result.returncode != 0, 'Invalid override succeeded')
        h.require(error in result.stderr, 'Missing error diagnostic: '+result.stderr)
        h.require(after == before, 'Validation failure changed config bytes/metadata')
    else:
        h.require(result.returncode == 0, 'Updater failed: '+result.stderr)
        h.require(after[0] == expected, f'Config differs: {after[0]!r} != {expected!r}')
        h.require(after[1].split(':')[:4] == before[1].split(':')[:4],
                  'Config inode, owner or permissions changed')
        repeated = invoke(h, server, path, environment)
        h.require(repeated.returncode == 0, 'Repeated update failed: '+repeated.stderr)
        h.require(snapshot(server, path) == after, 'Repeated update is not idempotent')
        if not environment or environment[0].startswith('UNRELATED='):
            h.require(after == before, 'No-override run modified config')
    h.require(not result.stdout, 'Updater must not print option values')


def file_cases(h):
    cases = [
        ('no-overrides', '# untouched\nftpd_banner=old', (), '# untouched\nftpd_banner=old', None),
        ('unrelated-multiline-env', 'ftpd_banner=old', ('UNRELATED=x\nCONF_ftpd_banner=injected',),
         'ftpd_banner=old', None),
        ('ignore-other-prefixes', 'ftpd_banner=old', ('conf_ftpd_banner=ignored', 'XCONF_ftpd_banner=ignored'),
         'ftpd_banner=old', None),
        ('replace-active', 'local_enable=YES\nwrite_enable=YES\n', ('CONF_WRITE_ENABLE=NO',),
         'local_enable=YES\nwrite_enable=NO\n', None),
        ('uncomment-whitespace', '# Keep this comment\n \t# \tchroot_local_user \t= NO\n',
         ('CONF_Chroot_Local_User=YES',), '# Keep this comment\nchroot_local_user=YES\n', None),
        ('append-sorted', '# Heading\n', ('CONF_max_per_ip=3', 'CONF_max_clients=10'),
         '# Heading\nmax_clients=10\nmax_per_ip=3\n', None),
        ('empty-config', '', ('CONF_ftpd_banner=new',), 'ftpd_banner=new\n', None),
        ('missing-final-newline', 'write_enable=YES', ('CONF_ftpd_banner=new',),
         'write_enable=YES\nftpd_banner=new\n', None),
        ('duplicates', '#write_enable=YES\nwrite_enable=NO\n # write_enable = YES\n',
         ('CONF_write_enable=NO',), 'write_enable=NO\n', None),
        ('exact-name', '# local_enable_note=keep\nlocal_enable=YES\n', ('CONF_local_enable=NO',),
         '# local_enable_note=keep\nlocal_enable=NO\n', None),
        ('empty-value', 'ftpd_banner=old\n', ('CONF_ftpd_banner=',), 'ftpd_banner=\n', None),
        ('same-case-aliases', '', ('CONF_FTPD_BANNER=same', 'CONF_ftpd_banner=same'),
         'ftpd_banner=same\n', None),
        ('conflicting-aliases', 'ftpd_banner=old\n', ('CONF_FTPD_BANNER=one', 'CONF_ftpd_banner=two'),
         None, 'conflicting CONF_ variables'),
        ('numeric-string-conflict', 'max_clients=10\n', ('CONF_MAX_CLIENTS=01', 'CONF_max_clients=1'),
         None, 'conflicting CONF_ variables'),
    ]
    for value in ('  spaces and tabs\t  ', r'/path/a&b;|=c\\d\1',
                  r'$(touch /tmp/CONF_EXECUTED) `touch /tmp/CONF_EXECUTED`',
                  '-n', r'-e\n', 'COMMENT', 'UNCOMMENT', 'Привет FTP'):
        cases.append(('literal-'+str(len(cases)), 'ftpd_banner=old\n', ('CONF_ftpd_banner='+value,),
                      'ftpd_banner='+value+'\n', None))
    for name in ('CONF_', 'CONF_1bad', 'CONF_bad.name', 'CONF_bad-name', 'CONF_bad[ab]'):
        cases.append(('invalid-name-'+name, 'write_enable=YES\n', (name+'=NO',),
                      None, 'invalid CONF_ parameter name'))
    for index, value in enumerate(('banner\nwrite_enable=NO', 'banner\rwrite_enable=NO', 'trailing\n')):
        cases.append(('invalid-multiline-'+str(index), 'write_enable=YES\n',
                      ('CONF_ftpd_banner='+value, 'CONF_write_enable=NO'), None, 'multiline value'))
    with h.Server(command=('sleep', '3600'), startup_wait=0) as server:
        for label, source, environment, expected, error in cases:
            h.check('config/render/'+label, lambda s=source, e=environment, x=expected, err=error:
                    render_case(h, server, s, e, x, err))
        h.check('config/files-and-errors', lambda: files_and_errors(h, server))


def files_and_errors(h, server):
    h.require(h.docker('exec', server.name, 'test', '!', '-e', '/tmp/CONF_EXECUTED',
                       check=False).returncode == 0, 'Option value executed as a command')
    missing = invoke(h, server, '/tmp/missing-config', ('CONF_write_enable=NO',))
    h.require(missing.returncode != 0 and 'existing writable file' in missing.stderr,
              'Missing configuration was not rejected')
    # No overrides must also work when no writable configuration is available.
    h.require(invoke(h, server, '/tmp/missing-config').returncode == 0,
              'No-op run unnecessarily requires a config')
    h.copy_files(server.name, [('tmp/readonly-config', b'write_enable=YES\n', 0o444, 0, 0)])
    before = snapshot(server, '/tmp/readonly-config')
    h.require(invoke(h, server, '/tmp/readonly-config', user='1000').returncode == 0,
              'No-op run requires write access')
    denied = invoke(h, server, '/tmp/readonly-config', ('CONF_write_enable=NO',), user='1000')
    h.require(denied.returncode != 0 and 'existing writable file' in denied.stderr,
              'Unwritable config was not rejected')
    h.require(snapshot(server, '/tmp/readonly-config') == before, 'Read-only file changed')

    h.copy_files(server.name, [('tmp/config-target', b'write_enable=YES\n', 0o600, 0, 0),
                               ('tmp/config-link', '/tmp/config-target', 0o777, 0, 0)])
    server.exec('ln', '/tmp/config-target', '/tmp/config-hardlink')
    result = invoke(h, server, '/tmp/config-link', ('CONF_write_enable=NO',))
    h.require(result.returncode == 0, result.stderr)
    h.require(server.exec('readlink', '/tmp/config-link').stdout.strip() == '/tmp/config-target',
              'Updater replaced symlink')
    h.require(server.exec('cat', '/tmp/config-hardlink').stdout == 'write_enable=NO\n',
              'Updater replaced target inode')

    before = snapshot(server, '/tmp/config-target')
    result = invoke(h, server, '/tmp/config-target', ('CONF_write_enable=YES', 'TMPDIR=/missing-tmp'))
    h.require(result.returncode != 0, 'Temporary file failure was ignored')
    h.require(snapshot(server, '/tmp/config-target') == before, 'Temp failure changed config')

    # Fault injection checks the final write status and temporary-file cleanup.
    h.copy_files(server.name, [('tmp/updater-bin', None, 0o755, 0, 0),
                               ('tmp/updater-bin/cat', b'#!/bin/sh\nexit 73\n', 0o755, 0, 0),
                               ('tmp/updater-work', None, 0o700, 0, 0)])
    result = invoke(h, server, '/tmp/config-target',
                    ('CONF_write_enable=YES', 'PATH=/tmp/updater-bin:/bin:/usr/bin',
                     'TMPDIR=/tmp/updater-work'))
    h.require(result.returncode == 73, 'Final write failure status was swallowed')
    h.require('update_conf: failed to write configuration' in result.stderr,
              'Final write failure lacks an updater diagnostic')
    h.require(not server.exec('ls', '-A', '/tmp/updater-work').stdout, 'Temporary file leaked')
    result = invoke(h, server, '/tmp/config-target',
                    ('CONF_ftpd_banner=invalid\nvalue', 'TMPDIR=/tmp/updater-work'))
    h.require(result.returncode != 0, 'Validation failure was swallowed')
    h.require(not server.exec('ls', '-A', '/tmp/updater-work').stdout, 'Validation leaked a temporary file')


def run(h):
    h.check('config/renderer-fixture', lambda: file_cases(h))
    import config_integration
    config_integration.run(h)
