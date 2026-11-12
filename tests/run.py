#!/usr/bin/env python3
"""Dependency-free Docker integration runner; failures are never xfailed."""
import argparse
import itertools
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ENV = {k: v for k, v in os.environ.items() if k not in
       ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")}
DOCKER = ["docker"]
RESULTS = []
ARGS = None


def docker(*args, check=True, timeout=180):
    return subprocess.run(DOCKER + list(args), env=ENV, text=True,
                          capture_output=True, check=check, timeout=timeout)


def copy_files(container, entries):
    """Copy explicit tar metadata, including root ownership, to a remote daemon.

    Entries are (path, data, mode, uid, gid). Data is bytes for a regular file,
    None for a directory, or a string symlink target.
    Paths are relative to the container root. No host bind mounts are required.
    """
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for path, data, mode, uid, gid in entries:
            info = tarfile.TarInfo(path)
            info.uid, info.gid, info.mode = uid, gid, mode
            if data is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif isinstance(data, str):
                info.type, info.linkname = tarfile.SYMTYPE, data
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    subprocess.run(DOCKER + ["cp", "-a", "-", container+":/"],
                   input=archive.getvalue(), env=ENV, check=True,
                   capture_output=True, timeout=180)


def check(name, function):
    started = time.monotonic()
    try:
        function()
    except Exception:
        detail = traceback.format_exc()
        for secret in ("test-pass-a", "test-pass-b", "test-pass-c"):
            detail = detail.replace(secret, "<redacted>")
        RESULTS.append(dict(id=name, status="failure", detail=detail,
                            seconds=time.monotonic()-started))
        print("FAIL", name, flush=True)
    else:
        RESULTS.append(dict(id=name, status="passed", seconds=time.monotonic()-started))
        print("PASS", name, flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Server:
    def __init__(self, users="alice|test-pass-a", security="plain", policy="default",
                 files=(), extra_args=(), extra_env=(), startup_wait=3, config=None,
                 autostart=True, command=()):
        self.name = "ftp-tests-" + uuid.uuid4().hex
        self.users, self.security, self.policy = users, security, policy
        self.files, self.extra_args, self.extra_env = files, extra_args, extra_env
        self.startup_wait, self.config = startup_wait, config
        self.autostart = autostart
        self.command = command

    def __enter__(self):
        try:
            docker("network", "create", "--label", "ftp-test.run="+self.name, self.name)
            docker("create", "--name", self.name, "--network", self.name,
                   "--network-alias", "ftp.test", "--label", "ftp-test.run="+self.name,
                   "-e", "USERS="+self.users, "-e", "ADDRESS=ftp.test",
                   *self.extra_args, *[arg for value in self.extra_env for arg in ("-e", value)],
                   *([] if self.security == "plain" else [
                       "-e", "TLS_CERT=/certs/cert.pem", "-e", "TLS_KEY=/certs/key.pem"]),
                   ARGS.image, *self.command)
            docker("cp", str(ARGS.certs)+"/.", self.name+":/certs")
            if self.policy == "readonly" or self.config is not None:
                conf = self.config if self.config is not None else (ROOT/"vsftpd.conf").read_text()
                if self.policy == "readonly":
                    conf = conf.replace("write_enable=YES", "write_enable=NO")
                # vsftpd rejects configs owned by the runner's non-root UID.
                copy_files(self.name, [("etc/vsftpd/vsftpd.conf", conf.encode(), 0o600, 0, 0)])
            if self.files:
                copy_files(self.name, self.files)
            if self.autostart:
                self.start()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def logs(self):
        r = docker("logs", self.name, check=False)
        return r.stdout+r.stderr

    def exec(self, *args):
        return docker("exec", self.name, *args)

    def state(self):
        return json.loads(docker("inspect", self.name).stdout)[0]["State"]

    def start(self):
        docker("start", self.name)
        # No exec/cp probes during daemonization; early-connect tests can opt out
        # of this observation interval and start an already prepared client.
        started = time.monotonic()
        while time.monotonic()-started < self.startup_wait:
            require(self.state()["Running"], "Container exited during startup: "+self.logs())
            time.sleep(.1)

    def __exit__(self, *exc):
        try:
            log = self.logs()
            # These are disposable credentials, nevertheless redact artifacts.
            for value in self.users.split():
                fields = value.split("|")
                if len(fields) > 1 and fields[1]:
                    log = log.replace(fields[1], "<redacted>")
            (ARGS.output/(self.name+".log")).write_text(log)
        finally:
            docker("rm", "-f", self.name, check=False)
            docker("network", "rm", self.name, check=False)


def protocols(security, policy):
    with Server(security=security, policy=policy) as server:
        if policy == "readonly":
            server.exec("sh", "-c", "mkdir -p /ftp/alice; printf existing-data > /ftp/alice/existing; chmod 644 /ftp/alice/existing")
        client = server.name+"-client"
        try:
            # Copy fixtures instead of bind mounts: works with remote daemons too.
            docker("create", "--name", client, "--network", server.name,
                   "-e", "TEST_SECURITY="+security, "-e", "TEST_POLICY="+policy,
                   ARGS.client_image, "python", "/tests/client.py")
            docker("cp", str(ROOT/"tests")+"/.", client+":/tests")
            docker("cp", str(ARGS.certs)+"/.", client+":/certs")
            docker("start", client)
            status = int(docker("wait", client).stdout.strip())
            r = docker("logs", client, check=False)
            (ARGS.output/(security+"-"+policy+".log")).write_text(r.stdout+r.stderr)
            destination = ARGS.output/(security+"-"+policy+".json")
            docker("cp", client+":/results/client.json", str(destination))
            rows = json.loads(destination.read_text())
            for row in rows:
                row["id"] = security+"/"+policy+"/"+row["id"]
            RESULTS.extend(rows)
            require(status == 0, "Client suite failed; see "+str(destination))
        finally:
            docker("rm", "-f", client, check=False)


def users(spec, expected):
    with Server(users=spec) as server:
        for name, uid, gid in expected:
            actual = server.exec("id", "-u", name).stdout.strip()
            if uid is not None:
                require(int(actual) == uid, f"{name}: UID {actual} != {uid}")
            if gid is not None:
                actual = server.exec("id", "-g", name).stdout.strip()
                require(int(actual) == gid, f"{name}: GID {actual} != {gid}")
            elif uid is None:
                primary = server.exec("id", "-gn", name).stdout.strip()
                require(primary == name, f"{name}: auto account inherited group {primary}")


def private_homes():
    with Server(users="alice|test-pass-a bob|test-pass-b") as server:
        for user in ("alice", "bob"):
            mode = server.exec("stat", "-c", "%a", "/ftp/"+user).stdout.strip()
            require(int(mode, 8) == 0o750, f"FS-003 {user}: expected private home0750, got {mode}")


def lifecycle():
    with Server() as server:
        before = server.exec("cat", "/var/run/vsftpd/vsftpd.pid").stdout.strip()
        result = docker("exec", server.name, "kill", before, check=False)
        # Namespace teardown may terminate the exec process after kill succeeds.
        require(result.returncode == 0 or not server.state()["Running"],
                "Could not signal the listener: "+result.stderr)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            state = json.loads(docker("inspect", server.name).stdout)[0]["State"]
            if not state["Running"]:
                return
            time.sleep(.1)
        raise AssertionError("LIFE-014: container remains alive without listener")


def write_report():
    failures = sum(r["status"] != "passed" for r in RESULTS)
    suite = ET.Element("testsuite", name="FTP Docker integration",
                       tests=str(len(RESULTS)), failures=str(failures))
    for row in RESULTS:
        case = ET.SubElement(suite, "testcase", name=row["id"], time=str(row.get("seconds", 0)))
        if row["status"] != "passed":
            ET.SubElement(case, "failure").text = row.get("detail", row["status"])
    ET.ElementTree(suite).write(ARGS.output/"junit.xml", encoding="utf-8", xml_declaration=True)
    (ARGS.output/"summary.json").write_text(json.dumps(RESULTS, indent=2))
    print(f"{len(RESULTS)} results; {failures} failures", flush=True)
    return failures


def main():
    global ARGS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ftp-under-test:local")
    parser.add_argument("--client-image", default="python:3.12-alpine")
    parser.add_argument("--output", type=Path, default=ROOT/"test-results")
    parser.add_argument("--suite", choices=("all", "protocols", "accounts", "regressions"), default="all")
    parser.add_argument("--startup-attempts", type=int, default=5,
                        help="independent early-connect containers per security profile")
    ARGS = parser.parse_args()
    if ARGS.startup_attempts < 1:
        parser.error("--startup-attempts must be positive")
    ARGS.output = ARGS.output.resolve()
    ARGS.output.mkdir(parents=True, exist_ok=True)
    docker("info")
    with tempfile.TemporaryDirectory(prefix="ftp-test-certs-") as tmp:
        ARGS.certs = Path(tmp)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "2", "-keyout", tmp+"/key.pem", "-out", tmp+"/cert.pem",
                        "-subj", "/CN=ftp.test", "-addext", "subjectAltName=DNS:ftp.test"],
                       check=True, capture_output=True)
        if ARGS.suite in ("all", "protocols"):
            for security, policy in itertools.product(("plain", "tls12", "tls13"), ("default", "readonly")):
                check("suite/"+security+"/"+policy, lambda s=security, p=policy: protocols(s, p))
        if ARGS.suite in ("all", "accounts"):
            account_checks()
        if ARGS.suite in ("all", "regressions"):
            import regressions
            regressions.run(sys.modules[__name__])
    return bool(write_report())


def account_checks():
    for spec, expected in [
        ("alice|test-pass-a", [("alice", None, None)]),
        ("alice|test-pass-a||10000", [("alice", 10000, 10000)]),
        ("alice|test-pass-a||10000|82", [("alice", 10000, 82)]),
        ("alice|test-pass-a|||82", [("alice", None, 82)]),
        ("alice|test-pass-a|||12000", [("alice", None, 12000)]),
    ]:
        check("USR/GRP/"+str(expected), lambda s=spec, e=expected: users(s, e))
    roles = [("auto", "alice|test-pass-a", ("alice", None, None)),
             ("explicit", "bob|test-pass-b||10000|12000", ("bob", 10000, 12000)),
             ("existing", "charlie|test-pass-c||10001|82", ("charlie", 10001, 82))]
    for permutation in itertools.permutations(roles):
        check("GRP-009/"+",".join(r[0] for r in permutation),
              lambda p=permutation: users(" ".join(r[1] for r in p), [r[2] for r in p]))
    check("FS-003/private-homes", private_homes)
    check("LIFE-014/listener-death", lifecycle)


if __name__ == "__main__":
    raise SystemExit(main())
