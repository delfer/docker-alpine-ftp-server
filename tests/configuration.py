"""CONF_ rendering checks run with the shipped shell, awk and updater."""
RUNTIME_PATH = '/tmp/rendered-config'


def invoke(h, server, path, environment=(), user=None, output=RUNTIME_PATH):
    args = ['exec']
    if user is not None:
        args += ['--user', user]
    for item in environment:
        args += ['-e', item]
    return h.docker(*args, server.name, '/bin/update_conf.sh', path, output, check=False)


def snapshot(server, path):
    return (server.exec('cat', path).stdout,
            server.exec('stat', '-L', '-c', '%i:%u:%g:%a:%y:%z', path).stdout)


def render_case(h, server, source, environment, expected=None, error=None):
    path = '/tmp/config-fixture'
    h.copy_files(server.name, [('tmp/config-fixture', source.encode(), 0o440, 0, 0),
                               ('tmp/rendered-config', b'previous generation', 0o600, 0, 0)])
    before = snapshot(server, path)
    previous = snapshot(server, RUNTIME_PATH)
    result = invoke(h, server, path, environment)
    h.require(snapshot(server, path) == before, 'Rendering changed source bytes/metadata')
    after = snapshot(server, RUNTIME_PATH)
    if error:
        h.require(result.returncode != 0, 'Invalid override succeeded')
        h.require(error in result.stderr, 'Missing error diagnostic: '+result.stderr)
        h.require(after == previous, 'Validation failure changed published runtime config')
    else:
        h.require(result.returncode == 0, 'Renderer failed: '+result.stderr)
        h.require(after[0] == expected, f'Config differs: {after[0]!r} != {expected!r}')
        h.require(server.exec('stat', '-c', '%u:%g:%a', RUNTIME_PATH).stdout.strip() == '0:0:600',
                  'Runtime config must be private and root-owned')
        repeated = invoke(h, server, path, environment)
        h.require(repeated.returncode == 0, 'Repeated render failed: '+repeated.stderr)
        h.require(snapshot(server, RUNTIME_PATH)[0] == after[0], 'Rendering is not idempotent')
        h.require(snapshot(server, path) == before, 'Repeated render changed the source')
    h.require(not result.stdout, 'Renderer must not print option values')


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
        h.check('config/removed-overrides', lambda: removed_overrides(h, server))


def files_and_errors(h, server):
    h.require(h.docker('exec', server.name, 'test', '!', '-e', '/tmp/CONF_EXECUTED',
                       check=False).returncode == 0, 'Option value executed as a command')
    for environment in ((), ('CONF_write_enable=NO',)):
        missing = invoke(h, server, '/tmp/missing-config', environment)
        h.require(missing.returncode != 0 and 'existing readable file' in missing.stderr,
                  'Missing source configuration was not rejected')
    h.copy_files(server.name, [('tmp/readonly-config', b'write_enable=YES\n', 0o444, 0, 0)])
    before = snapshot(server, '/tmp/readonly-config')
    result = invoke(h, server, '/tmp/readonly-config', ('CONF_write_enable=NO',))
    h.require(result.returncode == 0, result.stderr)
    h.require(snapshot(server, RUNTIME_PATH)[0] == 'write_enable=NO\n', 'Read-only source override ignored')
    h.require(snapshot(server, '/tmp/readonly-config') == before, 'Read-only source changed')

    h.copy_files(server.name, [('tmp/config-target', b'write_enable=YES\n', 0o600, 0, 0),
                               ('tmp/config-link', '/tmp/config-target', 0o777, 0, 0)])
    server.exec('ln', '/tmp/config-target', '/tmp/config-hardlink')
    before = snapshot(server, '/tmp/config-target')
    result = invoke(h, server, '/tmp/config-link', ('CONF_write_enable=NO',))
    h.require(result.returncode == 0, result.stderr)
    h.require(server.exec('readlink', '/tmp/config-link').stdout.strip() == '/tmp/config-target',
              'Renderer replaced source symlink')
    h.require(snapshot(server, '/tmp/config-hardlink') == before, 'Renderer changed source inode')
    for output in ('/tmp/config-target', '/tmp/config-link', '/tmp/config-hardlink'):
        result = invoke(h, server, '/tmp/config-target', ('CONF_write_enable=NO',), output=output)
        h.require(result.returncode != 0 and 'separate file' in result.stderr,
                  'Renderer accepted source/destination alias')
    h.require(snapshot(server, '/tmp/config-target') == before, 'Alias rejection changed source')

    h.copy_files(server.name, [('tmp/updater-bin', None, 0o755, 0, 0),
                               ('tmp/updater-bin/mv', b'#!/bin/sh\nexit 73\n', 0o755, 0, 0),
                               ('tmp/updater-bin/mktemp', b'#!/bin/sh\nexit 72\n', 0o755, 0, 0),
                               ('tmp/updater-work', None, 0o700, 0, 0),
                               ('tmp/updater-work/runtime.conf', b'last valid generation', 0o600, 0, 0)])
    output = '/tmp/updater-work/runtime.conf'
    previous = snapshot(server, output)
    environment = ('CONF_write_enable=NO', 'PATH=/tmp/updater-bin:/bin:/usr/bin')
    result = invoke(h, server, '/tmp/config-target', environment, output=output)
    h.require(result.returncode == 72, 'Temporary file creation failure was ignored')
    server.exec('rm', '/tmp/updater-bin/mktemp')
    result = invoke(h, server, '/tmp/config-target', environment, output=output)
    h.require(result.returncode == 73 and 'failed to publish runtime configuration' in result.stderr,
              'Atomic publication failure was swallowed')
    h.require(snapshot(server, output) == previous, 'Publication failure changed last valid generation')
    h.require(snapshot(server, '/tmp/config-target') == before, 'Publication failure changed source')
    result = invoke(h, server, '/tmp/config-target', ('CONF_ftpd_banner=invalid\nvalue',), output=output)
    h.require(result.returncode != 0, 'Validation failure was swallowed')
    h.require(snapshot(server, output) == previous, 'Validation changed last valid generation')
    h.require(server.exec('ls', '-A', '/tmp/updater-work').stdout == 'runtime.conf\n',
              'Failed rendering/publication leaked temporary files')


def removed_overrides(h, server):
    source = 'ftpd_banner=Custom source\nmax_clients=20\n'
    h.copy_files(server.name, [('tmp/removal-source', source.encode(), 0o440, 0, 0)])
    before = snapshot(server, '/tmp/removal-source')
    for environment, expected in [
        (('CONF_ftpd_banner=Override', 'CONF_max_clients=10', 'CONF_max_per_ip=3'),
         'ftpd_banner=Override\nmax_clients=10\nmax_per_ip=3\n'),
        (('CONF_max_clients=10',), 'ftpd_banner=Custom source\nmax_clients=10\n'),
        ((), source),
    ]:
        result = invoke(h, server, '/tmp/removal-source', environment)
        h.require(result.returncode == 0, result.stderr)
        h.require(snapshot(server, RUNTIME_PATH)[0] == expected, 'Removed override persisted in runtime config')
        h.require(snapshot(server, '/tmp/removal-source') == before, 'Rendering modified the source')


def run(h):
    h.check('config/renderer-fixture', lambda: file_cases(h))
    import config_integration
    config_integration.run(h)
