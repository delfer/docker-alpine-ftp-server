"""Exercise effective CONF_ settings through real FTP/FTPS connections."""
import ftplib
import io
import json
import os

from client import connect, SECURITY


def denied(function):
    try:
        function()
    except ftplib.error_perm as error:
        assert str(error).startswith('550'), str(error)
    else:
        raise AssertionError('Forbidden operation succeeded')


def main():
    scenario = json.loads(os.environ['TEST_CONFIG'])
    if scenario.get('reject_plaintext'):
        with ftplib.FTP('ftp.test', timeout=5) as ftp:
            try:
                ftp.login('alice', 'test-pass-a')
            except ftplib.error_perm as error:
                assert str(error).startswith('530'), str(error)
            else:
                raise AssertionError('TLS policy accepted a plaintext login')
    for method in ('PASV', 'EPSV', 'PORT', 'EPRT'):
        with connect(method) as ftp:
            assert ftp.getwelcome() == '220 '+scenario['banner'], ftp.getwelcome()
            if SECURITY != 'plain':
                expected = 'TLSv1.3' if SECURITY == 'tls13' else 'TLSv1.2'
                assert ftp.sock.version() == expected, ftp.sock.version()
                assert ftp._prot_p, 'Data channel protection was not enabled'
            if scenario.get('chroot'):
                assert ftp.pwd() == '/', ftp.pwd()
                ftp.cwd('..')
                assert ftp.pwd() == '/', 'Escaped chroot'
                denied(lambda: ftp.cwd('/etc'))
            if method == 'PASV':
                address, port = ftp.makepasv()
                assert address == ftp.sock.getpeername()[0], address
                assert scenario['min_port'] <= port <= scenario['max_port'], port
            elif method == 'EPSV':
                _, port = ftplib.parse229(ftp.sendcmd('EPSV'), ftp.sock.getpeername())
                assert scenario['min_port'] <= port <= scenario['max_port'], port
            if scenario.get('readonly'):
                received = bytearray()
                ftp.retrbinary('RETR existing', received.extend)
                assert received == b'existing-data', received
                for command in ('STOR new', 'APPE existing', 'DELE existing', 'MKD new'):
                    if command.startswith(('STOR', 'APPE')):
                        denied(lambda c=command: ftp.storbinary(c, io.BytesIO(b'forbidden')))
                    else:
                        denied(lambda c=command: ftp.sendcmd(c))
            else:
                name = 'config-'+method+'.bin'
                payload = b'CONF_ roundtrip\x00\xff\n'*4096
                ftp.storbinary('STOR '+name, io.BytesIO(payload))
                assert name in ftp.nlst(), 'Uploaded file not listed'
                received = bytearray()
                ftp.retrbinary('RETR '+name, received.extend)
                assert received == payload, 'Transferred bytes differ'
            assert method in [command.split()[0] for command in ftp.trace], ftp.trace
        print('PASS', SECURITY, method, flush=True)


if __name__ == '__main__':
    main()
