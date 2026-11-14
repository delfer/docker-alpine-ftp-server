# Docker and Kubernetes secrets

Set `USERS_FILE` to a mounted text file containing the same entries as `USERS`:
`name|password|[home]|[uid]|[gid]`. Entries may be separated by spaces, tabs or
newlines; a final newline is optional. Spaces, tabs, newlines and `|` cannot be
part of a field. Backslashes and shell metacharacters in passwords are literal.

`USERS` and `USERS_FILE` are mutually exclusive, including explicitly empty
values. An empty path, missing/unreadable/non-regular file or empty/whitespace-only
content stops startup before accounts are changed. It never enables the default
account as a fallback. Account/group creation failures also stop startup.
Matching non-root accounts with custom home paths are recreated on restart,
just like accounts under `/ftp`; their home contents remain in place. This also
applies rotated passwords and UID/GID settings to custom-home accounts.
With neither variable set, or with only `USERS=''`, the existing default account
remains unchanged.

The loader follows symlinks, reads once per start, leaves the source unchanged,
and does not print or export file credentials. Keep the file owned/readable only
by the container's root account and mount it read-only. FTP users are not
chrooted by default: a broadly readable secret could be downloaded over FTP.
Only `USERS_FILE` is supported;
`TLS_CERT` and `TLS_KEY` already accept paths to certificate/key files.

## Docker Compose

Create a local `users` file with your credentials. With a regular rootful Docker
daemon on Linux, use `sudo chown 0:0 users` and `sudo chmod 400 users` so only
container root can read it. With user namespaces, map ownership to container
root instead. Do not commit this file to version control.

```yaml
services:
  ftp:
    image: delfer/alpine-ftp-server
    ports:
      - '21:21'
      - '21000-21010:21000-21010'
    environment:
      USERS_FILE: /run/secrets/ftp_users
      ADDRESS: '127.0.0.1' # Use the server's reachable IP/DNS for remote clients.
    secrets:
      - ftp_users
    volumes:
      - './data:/ftp'
secrets:
  ftp_users:
    file: ./users
```

A read-only bind mount works too: replace `-e USERS=...` in a `docker run`
command with `-e USERS_FILE=/run/secrets/ftp_users` and
`--mount type=bind,src="$PWD/users",dst=/run/secrets/ftp_users,readonly`.

## Kubernetes Secret and ConfigMap directories

No Kubernetes API integration is needed. Create a Secret from your `users` file
and a ConfigMap from a complete `vsftpd.conf` (for example, the repository's):

```sh
kubectl create secret generic ftp-users --from-file=users=./users
kubectl create configmap ftp-config --from-file=vsftpd.conf=./vsftpd.conf
```

Mount the directories in the Pod spec (or a Deployment's `spec.template.spec`):

```yaml
containers:
  - name: ftp
    image: delfer/alpine-ftp-server
    env:
      - name: USERS_FILE
        value: /run/secrets/ftp/users
    volumeMounts:
      - name: users
        mountPath: /run/secrets/ftp
        readOnly: true
      - name: config
        mountPath: /etc/vsftpd
        readOnly: true
volumes:
  - name: users
    secret:
      secretName: ftp-users
      defaultMode: 0400
  - name: config
    configMap:
      name: ftp-config
```

The ConfigMap must contain `vsftpd.conf`; mounting the directory hides the image's
copy. It must remain root-owned, as required by vsftpd. `CONF_*` overrides still
work because the runtime config is generated separately in `/var/run/vsftpd`.
FTP exposure and passive-address/port settings depend on your cluster network.
Keep the Secret's explicit `0400` mode: Kubernetes' default `0644` would make the
credentials readable by FTP accounts.

Kubernetes' projected `..data` symlinks work for both mounts. Once an updated
Secret/ConfigMap has been projected, restart the container (or roll out new Pods)
to apply it. Existing sessions keep their current settings until restart;
`SIGHUP` does not reload secrets or regenerate the runtime config. `subPath`
mounts do not receive projected updates; recreate Pods to update those mounts.
