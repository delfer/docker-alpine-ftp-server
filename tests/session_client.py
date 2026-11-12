"""JSON-line control of real FTP sessions while the host tests process lifecycle."""
import concurrent.futures
import ftplib
import io
import itertools
import json
import os
import socket
import struct
import sys
import threading
import time
import traceback
import uuid

from client import connect as protocol_connect

CONFIG = json.loads(os.environ['TEST_SCENARIO'])
CREDENTIALS = CONFIG['credentials']
SESSIONS = {}
DATA = {}
PERSIST = {}
SEQUENCE = itertools.count()


def connect(user, method='PASV', password=None):
    ftp = protocol_connect(method, user, CREDENTIALS[user] if password is None else password)
    expected = CONFIG.get('homes', {}).get(user, '/ftp/'+user)
    if ftp.pwd() != expected:
        ftp.close()
        raise AssertionError('Unexpected home for '+user)
    return ftp


def transfer(ftp, user, name=None, payload=None):
    name = name or 'audit-'+user+'-'+str(next(SEQUENCE))+'-'+uuid.uuid4().hex+'.bin'
    if payload is None:
        payload = ((user+':'+name).encode()*3000)[:65537]
    ftp.storbinary('STOR '+name, io.BytesIO(payload))
    received = bytearray()
    ftp.retrbinary('RETR '+name, received.extend)
    if bytes(received) != payload:
        raise AssertionError('Transferred bytes differ for '+user)
    return [dict(user=user, file=name, operation=op) for op in ('UPLOAD', 'DOWNLOAD')]


def handle(command):
    op = command['op']
    if op == 'ready':
        deadline = time.monotonic()+5
        while True:
            try:
                ftp = connect(next(iter(CREDENTIALS)))
            except (ConnectionRefusedError, socket.gaierror):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.02)
            else:
                ftp.quit()
                return {}
        # EOF, TLS errors and login failures after connect are never retried.
    if op == 'open':
        user = command['user']
        SESSIONS[command['id']] = (user, connect(user, command.get('method', 'PASV')))
        return {}
    if op == 'close':
        _, ftp = SESSIONS.pop(command['id'])
        if command.get('abrupt'):
            ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            ftp.close()
        else:
            ftp.quit()
        return {}
    if op == 'noop':
        return dict(reply=SESSIONS[command['id']][1].voidcmd('NOOP'))
    if op == 'transfer':
        user, ftp = SESSIONS[command['id']]
        return dict(events=transfer(ftp, user))
    if op == 'persistent':
        events = []
        for user in CREDENTIALS:
            with connect(user) as ftp:
                name = 'persist-'+user+'.bin'
                if command.get('verify'):
                    received = bytearray()
                    ftp.retrbinary('RETR '+name, received.extend)
                    if bytes(received) != PERSIST[user]:
                        raise AssertionError('Persistent bytes differ for '+user)
                    events.append(dict(user=user, file=name, operation='DOWNLOAD'))
                else:
                    PERSIST[user] = (user.encode()+b'\0persistent\xff')*1234
                    events.extend(transfer(ftp, user, name, PERSIST[user]))
                if command.get('private', True):
                    for other in CREDENTIALS:
                        if other != user:
                            try:
                                ftp.cwd(CONFIG.get('homes', {}).get(other, '/ftp/'+other))
                            except ftplib.error_perm as error:
                                if not str(error).startswith('550'):
                                    raise
                            else:
                                raise AssertionError(user+' entered private home of '+other)
        return dict(events=events)
    if op == 'read_peer':
        user, owner = command['user'], command['owner']
        path = '/ftp/'+owner+'/persist-'+owner+'.bin'
        with connect(user) as ftp:
            data = bytearray()
            ftp.retrbinary('RETR '+path, data.extend)
            if bytes(data) != PERSIST[owner]:
                raise AssertionError('Shared-group read returned different bytes')
        return dict(events=[dict(user=user, file=path, operation='DOWNLOAD')])
    if op == 'parallel':
        roles = [(u, m) for u in CREDENTIALS for m in ('PASV', 'EPSV', 'PORT', 'EPRT')]
        barrier = threading.Barrier(len(roles), timeout=15)
        def worker(role):
            user, method = role
            events = []
            with connect(user, method) as ftp:
                barrier.wait()
                for _ in range(4):
                    events.extend(transfer(ftp, user))
            return events
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(roles)) as pool:
            groups = list(pool.map(worker, roles))
        return dict(events=[event for group in groups for event in group])
    if op == 'churn':
        users = list(CREDENTIALS)
        for index in range(30):
            ftp = connect(users[index % len(users)])
            if index % 2:
                ftp.quit()
            else:
                ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                ftp.close()
        return {}
    if op == 'begin_upload':
        user, ftp = SESSIONS[command['id']]
        ftp.voidcmd('TYPE I')
        name = 'interrupted-'+user+'-'+uuid.uuid4().hex+'.bin'
        data = ftp.transfercmd('STOR '+name)
        data.sendall(b'a'*262144)
        DATA[command['id']] = data
        return dict(user=user, file=name)
    if op == 'broken':
        closed, terminal_replies = [], []
        for key in command['ids']:
            _, ftp = SESSIONS.pop(key)
            deadline = time.monotonic()+2
            messages = []
            try:
                # A dying process may emit one or several fatal diagnostics;
                # concurrent handlers can even duplicate their prefixes. Read
                # to actual EOF/reset without sending another FTP command.
                while True:
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Session did not close: '+key)
                    ftp.sock.settimeout(remaining)
                    try:
                        reply = ftp.getresp()
                    except (ftplib.error_temp, ftplib.error_perm, ftplib.error_proto) as error:
                        message = str(error)
                        for password in CREDENTIALS.values():
                            message = message.replace(password, '<redacted>')
                        messages.append(message)
                    except (OSError, EOFError) as ending:
                        if isinstance(ending, TimeoutError):
                            raise
                        closed.append(key)
                        break
                    else:
                        raise AssertionError('Unexpected reply after process death: '+reply)
            finally:
                ftp.close()
                if key in DATA:
                    DATA.pop(key).close()
            terminal_replies.append(dict(id=key, messages=messages))
        return dict(closed=closed, terminal_replies=terminal_replies)
    if op == 'config':
        with connect(next(iter(CREDENTIALS))) as ftp:
            if command['banner'] not in ftp.getwelcome():
                raise AssertionError('Custom banner ignored')
            _, port = ftp.makepasv()
            if not command['min_port'] <= port <= command['max_port']:
                raise AssertionError('Passive range ignored: '+str(port))
            return dict(events=transfer(ftp, next(iter(CREDENTIALS)), 'custom-config.bin'))
    if op == 'reset':
        for _, ftp in SESSIONS.values():
            ftp.close()
        for data in DATA.values():
            data.close()
        SESSIONS.clear()
        DATA.clear()
        return {}
    raise ValueError('Unknown operation: '+op)


if __name__ == '__main__':
    for line in sys.stdin:
        try:
            print(json.dumps(dict(ok=True, **handle(json.loads(line)))), flush=True)
        except Exception:
            detail = traceback.format_exc()
            for password in CREDENTIALS.values():
                detail = detail.replace(password, '<redacted>')
            print(json.dumps(dict(ok=False, detail=detail)), flush=True)
    handle(dict(op='reset'))
