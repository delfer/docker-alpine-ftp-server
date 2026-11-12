"""Real FTP protocol tests. Run inside the isolated client container via run.py."""
import ftplib
import concurrent.futures
import io
import json
import os
import random
import socket
import ssl
import time
import unittest
import uuid
from pathlib import Path

SECURITY = os.environ["TEST_SECURITY"]
POLICY = os.environ.get("TEST_POLICY", "default")


class ExactFTP(ftplib.FTP):
    method = "PASV"

    def putcmd(self, line):
        self.trace.append("PASS <redacted>" if line.startswith("PASS ") else line)
        return super().putcmd(line)

    def makepasv(self):
        if self.method == "EPSV":
            return ftplib.parse229(self.sendcmd("EPSV"), self.sock.getpeername())
        return ftplib.parse227(self.sendcmd("PASV"))

    def makeport(self):
        listener = socket.create_server((self.sock.getsockname()[0], 0))
        listener.settimeout(self.timeout)
        try:
            address, port = listener.getsockname()
            if self.method == "EPRT":
                self.sendeprt(address, port)
            else:
                self.sendport(address, port)
            return listener
        except BaseException:
            listener.close()
            raise


class ExactTLS(ExactFTP, ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            try:
                conn = self.context.wrap_socket(
                    conn, server_hostname=self.host, session=self.sock.session
                )
            except BaseException:
                conn.close()
                raise
        return conn, size


def context():
    ctx = ssl.create_default_context(cafile="/certs/cert.pem")
    version = ssl.TLSVersion.TLSv1_3 if SECURITY == "tls13" else ssl.TLSVersion.TLSv1_2
    ctx.minimum_version = ctx.maximum_version = version
    return ctx


def connect(method="PASV", user="alice", password="test-pass-a", login=True):
    ftp = ExactFTP() if SECURITY == "plain" else ExactTLS(context=context())
    ftp.trace = []
    ftp.method = method
    ftp.set_pasv(method in ("PASV", "EPSV"))
    try:
        ftp.connect("ftp.test", 21, timeout=5)
        if login:
            ftp.login(user, password)
            if SECURITY != "plain":
                ftp.prot_p()
        return ftp
    except BaseException:
        ftp.close()
        raise


class Files(unittest.TestCase):
    method = "PASV"

    def setUp(self):
        self.ftp = connect(self.method)
        self.addCleanup(self.ftp.close)
        self.folder = "test-" + uuid.uuid4().hex
        self.ftp.mkd(self.folder)
        self.ftp.cwd(self.folder)

    def upload(self, name, data):
        self.assertTrue(self.ftp.storbinary("STOR " + name, io.BytesIO(data)).startswith("226"))

    def download(self, name, rest=None):
        data = bytearray()
        self.assertTrue(self.ftp.retrbinary("RETR " + name, data.extend, rest=rest).startswith("226"))
        return bytes(data)

    def roundtrip(self, size=4352, name="data.bin"):
        payload = random.Random(372 + size).randbytes(size)
        self.upload(name, payload)
        self.assertEqual(self.download(name), payload)
        self.assertEqual(self.ftp.size(name), size)
        self.ftp.delete(name)
        self.assertIn(self.method, [c.split(" ", 1)[0] for c in self.ftp.trace])
        others = {"PASV", "EPSV", "PORT", "EPRT"} - {self.method}
        self.assertFalse(others.intersection(c.split(" ", 1)[0] for c in self.ftp.trace))

    def test_DATA_006_overwrite(self):
        self.upload("f", b"long" * 300)
        self.upload("f", b"short")
        self.assertEqual(self.download("f"), b"short")

    def test_DATA_007_append(self):
        self.upload("f", b"first")
        self.ftp.storbinary("APPE f", io.BytesIO(b"second"))
        self.assertEqual(self.download("f"), b"firstsecond")

    def test_DATA_008_resume(self):
        self.upload("f", bytes(range(256)) * 4)
        for offset in (0, 1, 500, 1024):
            self.assertEqual(self.download("f", offset), (bytes(range(256)) * 4)[offset:])

    def test_DATA_011_rename(self):
        self.upload("a", b"rename")
        self.ftp.rename("a", "b")
        self.assertEqual(self.download("b"), b"rename")
        with self.assertRaises(ftplib.error_perm):
            self.download("a")

    def test_DATA_013_directories(self):
        self.ftp.mkd("sub")
        self.ftp.cwd("sub")
        self.assertTrue(self.ftp.pwd().endswith("/sub"))
        self.ftp.cwd("..")
        self.ftp.rmd("sub")

    def test_DATA_014_nonempty_directory(self):
        self.upload(".hidden", b"hidden")
        self.ftp.cwd("..")
        with self.assertRaises(ftplib.error_perm):
            self.ftp.rmd(self.folder)

    def test_DATA_015_missing_and_recovery(self):
        for command in ("RETR missing", "SIZE missing", "DELE missing", "CWD missing", "RMD missing"):
            with self.subTest(command=command), self.assertRaises(ftplib.error_perm):
                if command.startswith("RETR"):
                    self.ftp.retrbinary(command, lambda _: None)
                else:
                    self.ftp.sendcmd(command)
        self.roundtrip()

    def test_DATA_017_empty_listing(self):
        self.assertEqual(self.ftp.nlst(), [])

    def test_DATA_034_repeated_transfers(self):
        for size in range(10):
            self.roundtrip(size)

    def test_MODE_switch(self):
        self.upload("f", b"switch")
        for method in ("PASV", "PORT", "EPSV", "EPRT"):
            self.ftp.method = method
            self.ftp.set_pasv(method in ("PASV", "EPSV"))
            self.assertEqual(self.download("f"), b"switch")


for method in ("PASV", "EPSV", "PORT", "EPRT"):
    attrs = {"method": method}
    for size in (0, 1, 8191, 8192, 8193, 65535, 65536, 65537, 16777216):
        def test_size(self, size=size):
            self.roundtrip(size)
        attrs["test_MX_PAYLOAD_" + str(size)] = test_size
    for index, name in enumerate(("plain.txt", "with space.txt", "кириллица.txt", "日本語.txt",
                                  "emoji-😀.txt", "a;b", "a$b", "a&b", "a|b", 'a"b', "-leading", ".hidden")):
        def test_name(self, name=name):
            self.roundtrip(name=name)
        attrs["test_MX_NAMES_" + str(index)] = test_name
    globals()["Files_" + method] = type("Files_" + method, (Files,), attrs)


class Control(unittest.TestCase):
    def test_PAR_001_parallel_clients(self):
        def transfer(method):
            name = "parallel-" + uuid.uuid4().hex
            payload = random.Random(method).randbytes(65537)
            with connect(method) as ftp:
                ftp.storbinary("STOR " + name, io.BytesIO(payload))
                data = bytearray()
                ftp.retrbinary("RETR " + name, data.extend)
                ftp.delete(name)
                self.assertEqual(bytes(data), payload)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(transfer, ("PASV", "EPSV", "PORT", "EPRT")))

    def test_AUTH_011_unknown_command(self):
        with connect() as ftp:
            with self.assertRaises(ftplib.error_perm):
                ftp.sendcmd("NOT_A_COMMAND")
            self.assertTrue(ftp.voidcmd("NOOP").startswith("200"))

    def test_FS_006_default_no_chroot(self):
        with connect() as ftp:
            ftp.cwd("/")
            self.assertEqual(ftp.pwd(), "/")

    def test_DATA_019_dotfile_policy(self):
        with connect() as ftp:
            folder = "hidden-" + uuid.uuid4().hex
            ftp.mkd(folder)
            ftp.cwd(folder)
            ftp.storbinary("STOR .hidden", io.BytesIO(b"hidden"))
            self.assertNotIn(".hidden", ftp.nlst())
            self.assertIn(".hidden", ftp.nlst("-a"))
            ftp.delete(".hidden")
            ftp.cwd("..")
            ftp.rmd(folder)

    def test_AUTH_002_invalid_password(self):
        with self.assertRaisesRegex(ftplib.error_perm, "^530"):
            connect(password="incorrect")

    def test_AUTH_003_unknown(self):
        with self.assertRaisesRegex(ftplib.error_perm, "^530"):
            connect(user="missing")

    def test_AUTH_004_anonymous(self):
        with self.assertRaises(ftplib.error_perm):
            connect(user="anonymous")

    def test_AUTH_005_prelogin(self):
        with connect(login=False) as ftp:
            for cmd in ("CWD /", "DELE missing", "MKD denied"):
                with self.subTest(cmd=cmd), self.assertRaises(ftplib.error_perm):
                    ftp.sendcmd(cmd)

    def test_AUTH_010_commands(self):
        with connect() as ftp:
            for cmd in ("SYST", "FEAT", "HELP", "NOOP", "TYPE I", "TYPE A", "PWD"):
                self.assertIn(ftp.sendcmd(cmd)[0], "23")

    def test_LIFE_002_disconnect(self):
        for _ in range(5):
            with connect() as ftp:
                ftp.quit()
        with connect() as ftp:
            self.assertTrue(ftp.pwd())

    def test_NET_range(self):
        with connect() as ftp:
            for _ in range(15):
                _, port = ftp.makepasv()
                self.assertTrue(21000 <= port <= 21010)


class TLS(unittest.TestCase):
    def test_TLS_022_plain_login_forbidden(self):
        with ftplib.FTP() as ftp:
            ftp.connect("ftp.test", timeout=5)
            with self.assertRaises(ftplib.error_perm):
                ftp.login("alice", "test-pass-a")

    def test_TLS_025_no_reuse(self):
        with ftplib.FTP_TLS(context=context()) as ftp:
            ftp.connect("ftp.test", timeout=5)
            ftp.login("alice", "test-pass-a")
            ftp.prot_p()
            with self.assertRaisesRegex(ftplib.error_perm, "^522"):
                ftp.nlst()

    def test_TLS_023_plain_data_forbidden(self):
        with connect() as ftp:
            ftp.prot_c()
            with self.assertRaises(ftplib.error_perm):
                ftp.nlst()

    def test_TLS_013_untrusted(self):
        with ftplib.FTP_TLS(context=ssl.create_default_context()) as ftp:
            ftp.connect("ftp.test", timeout=5)
            with self.assertRaises(ssl.SSLCertVerificationError):
                ftp.auth()

    def test_TLS_014_hostname(self):
        with ftplib.FTP_TLS(context=context()) as ftp:
            ftp.connect("ftp.test", timeout=5)
            ftp.host = "wrong.test"
            with self.assertRaises(ssl.SSLCertVerificationError):
                ftp.auth()

    def test_TLS_019_legacy(self):
        for version in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1):
            ctx = context()
            ctx.minimum_version = ctx.maximum_version = version
            ctx.set_ciphers("ALL:@SECLEVEL=0")
            with self.subTest(version=version), ftplib.FTP_TLS(context=ctx) as ftp:
                ftp.connect("ftp.test", timeout=5)
                with self.assertRaises(ssl.SSLError) as caught:
                    ftp.auth()
                self.assertIn("ALERT_PROTOCOL_VERSION", str(caught.exception))


class ReadOnly(unittest.TestCase):
    def test_CFG_003_mutations(self):
        for method in ("PASV", "EPSV", "PORT", "EPRT"):
            with self.subTest(method=method), connect(method) as ftp:
                data = bytearray()
                ftp.retrbinary("RETR existing", data.extend)
                self.assertEqual(bytes(data), b"existing-data")
                for cmd in ("STOR new", "APPE existing", "DELE existing", "MKD new"):
                    with self.subTest(command=cmd), self.assertRaises(ftplib.error_perm):
                        if cmd.startswith(("STOR", "APPE")):
                            ftp.storbinary(cmd, io.BytesIO(b"forbidden"))
                        else:
                            ftp.sendcmd(cmd)


class Record(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()

    def addSuccess(self, test):
        super().addSuccess(test)
        records.append(dict(id=test.id(), seconds=time.monotonic()-self.started, status="passed"))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        records.append(dict(id=test.id(), status="failure", detail=self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        super().addError(test, err)
        records.append(dict(id=test.id(), status="error", detail=self._exc_info_to_string(err, test)))

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            records.append(dict(id=str(subtest), status="failure", detail=self._exc_info_to_string(err, test)))


if __name__ == "__main__":
    Path("/results").mkdir(exist_ok=True)
    records = []
    loader = unittest.TestLoader()
    classes = [ReadOnly] if POLICY == "readonly" else [
        globals()["Files_" + m] for m in ("PASV", "EPSV", "PORT", "EPRT")
    ] + [Control] + ([TLS] if SECURITY != "plain" else [])
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(cls) for cls in classes)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Record).run(suite)
    Path("/results/client.json").write_text(json.dumps(records, ensure_ascii=False))
    raise SystemExit(not result.wasSuccessful())
