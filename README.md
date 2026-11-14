# docker-alpine-ftp-server

[![Build Status](https://img.shields.io/github/actions/workflow/status/delfer/docker-alpine-ftp-server/docker-publish-image.yml?branch=master&style=flat-square&logo=github&label=build)](https://github.com/delfer/docker-alpine-ftp-server/actions/workflows/docker-publish-image.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/delfer/alpine-ftp-server?style=flat-square&logo=docker)](https://hub.docker.com/r/delfer/alpine-ftp-server/)
[![Docker Stars](https://img.shields.io/docker/stars/delfer/alpine-ftp-server?style=flat-square&logo=docker)](https://hub.docker.com/r/delfer/alpine-ftp-server/)
[![Docker Image Size (latest)](https://img.shields.io/docker/image-size/delfer/alpine-ftp-server/latest?style=flat-square&logo=docker&label=image%20size)](https://hub.docker.com/r/delfer/alpine-ftp-server/tags?name=latest)

Small FTP/FTPS Docker image based on Alpine Linux 3.24.4 and vsftpd 3.0.5.

## Quick start

Save as `compose.yaml`, replace the password, then run `docker compose up -d`:

```yaml
services:
  ftp:
    image: delfer/alpine-ftp-server
    ports:
      - '21:21'
      - '21000-21010:21000-21010'
    environment:
      USERS: 'one|change-this-password'
      ADDRESS: '127.0.0.1'
    volumes:
      - './data:/ftp'
```

This works for clients on the Docker host. For remote clients, set `ADDRESS` to
its reachable server IP/DNS name and allow the published ports through the
firewall. Uploaded files persist in `./data/one`.

## Custom vsftpd options

Add these keys to the service's `environment` mapping. Quote YAML values such as
`'YES'`, `'NO'` and numbers.

| Goal | Settings |
| --- | --- |
| Confine users to their home | `CONF_chroot_local_user: 'YES'`, `CONF_allow_writeable_chroot: 'YES'` |
| Read-only FTP access | `CONF_write_enable: 'NO'` |
| Custom banner | `CONF_ftpd_banner: 'Welcome FTP Server'` |
| New uploads with mode 0664 | `CONF_local_umask: '002'` |
| Include hidden files in listings | `CONF_force_dot_files: 'YES'` |
| Control port 2121 | `CONF_listen_port: '2121'` and port mapping `'2121:2121'` |
| Larger passive range | `MIN_PORT: '30000'`, `MAX_PORT: '30100'` and mapping `'30000-30100:30000-30100'` |

After environment changes, run `docker compose up -d --force-recreate`.
`docker compose restart` keeps the previous environment. Chroot and hidden-file
visibility remain opt-in; umask does not change existing filesystem permissions.

`USERS` accepts space-separated entries: `name|password|[home]|[uid]|[gid]`.
For example, `USERS: 'one|password1 two|password2'` creates two users.
Use mapping-style YAML as shown; `- USERS="one|password"` can include literal
quotes in the username.

## More examples

- [Anonymous downloads](docs/configuration.md#anonymous-downloads)
- [Read-only access for one user](docs/configuration.md#read-only-access-for-one-user)
- [Local timestamps](docs/configuration.md#local-timestamps)
- [FTPS with certificates](docs/configuration.md#ftps)
- [Own config file and all CONF_* details](docs/configuration.md#custom-vsftpd-options)

Custom configs still mount at `/etc/vsftpd/vsftpd.conf`, including read-only,
with root ownership. Each start generates a separate runtime config; removing a
`CONF_*` override restores the source setting. Restart to reread source edits;
`SIGHUP` alone does not regenerate it.
