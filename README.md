# docker-alpine-ftp-server

[![Build Status](https://img.shields.io/github/actions/workflow/status/delfer/docker-alpine-ftp-server/docker-publish-image.yml?branch=master&style=flat-square&logo=github&label=build)](https://github.com/delfer/docker-alpine-ftp-server/actions/workflows/docker-publish-image.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/delfer/alpine-ftp-server?style=flat-square&logo=docker)](https://hub.docker.com/r/delfer/alpine-ftp-server/)
[![Docker Stars](https://img.shields.io/docker/stars/delfer/alpine-ftp-server?style=flat-square&logo=docker)](https://hub.docker.com/r/delfer/alpine-ftp-server/)
[![Docker Image Size (latest)](https://img.shields.io/docker/image-size/delfer/alpine-ftp-server/latest?style=flat-square&logo=docker&label=image%20size)](https://hub.docker.com/r/delfer/alpine-ftp-server/tags?name=latest)

Small and flexible docker image with vsftpd server

Built with Alpine Linux 3.24.4 and vsftpd 3.0.5 (Alpine package 3.0.5-r3).
The base image and vsftpd package can be overridden with the `BASE_IMG` and
`VSFTPD_VERSION` build arguments.

## Usage
```
docker run -d \
    -p "21:21" \
    -p 21000-21010:21000-21010 \
    -e USERS="one|1234" \
    -e ADDRESS=ftp.site.domain \
    delfer/alpine-ftp-server
```

## Configuration

Environment variables:
- `USERS` - space and `|` separated list (optional, default: `alpineftp|alpineftp`)
  - format `name1|password1|[folder1][|uid1][|gid1] name2|password2|[folder2][|uid2][|gid2]`
- `ADDRESS` - external address to which clients can connect for passive ports (optional, should resolve to ftp server ip address)
- `MIN_PORT` - minimum port number to be used for passive connections (optional, default `21000`)
- `MAX_PORT` - maximum port number to be used for passive connections (optional, default `21010`)
- `CONF_<OPTION>` - set a vsftpd configuration option (optional; option names are case-insensitive, prefix is `CONF_`)

When upgrading from master at `981ebce` (before `CONF_` support), no data/config
conversion is needed for the existing
environment variables and source-config mounts. Review any previously unused
`CONF_` variables: this prefix is now interpreted as vsftpd options.

## Custom vsftpd options

For example, add these arguments to `docker run`:

```sh
-e CONF_FTPD_BANNER='My FTP server' \
-e CONF_local_umask=077 \
-e CONF_max_clients=10
```

`CONF_<OPTION>` replaces an existing assignment, activates a commented example,
or appends a missing option in the generated runtime configuration. Each start
reads `/etc/vsftpd/vsftpd.conf` as the source and writes the effective config to
`/var/run/vsftpd/vsftpd.conf`. Repeated rendering produces the same contents;
matching duplicates become one assignment. Other options and comments are
retained. Values are literal, including spaces, `=`, `&`, `/`,
`|` and backslashes. An empty value sets an empty string; it does not remove an
option. There are no special comment/uncomment action values.

Names must match `[A-Za-z][A-Za-z0-9_]*`. Conflicting variables such as
`CONF_FTPD_BANNER=one` and `CONF_ftpd_banner=two`, and values containing CR/LF,
fail startup before publishing a runtime config. vsftpd validates option names and
types; unsupported options or invalid values fail startup. Values are not
printed by the updater.
Native vsftpd validation failures may exit without a diagnostic in Docker logs;
inspect the exit status and rendered configuration when troubleshooting.

The config is loaded after the existing `MIN_PORT`, `MAX_PORT`, `ADDRESS` and
`TLS_CERT`/`TLS_KEY` command-line settings, so explicit `CONF_` values take
precedence. For example, `CONF_pasv_min_port`/`CONF_pasv_max_port` override the
passive range; publish the corresponding Docker ports too. TLS overrides can
change the policy selected by `TLS_CERT`/`TLS_KEY`. Options that change how the
daemon runs (such as `background` or `listen`) must remain compatible with the
container startup and supervision model.

The source config is always left unchanged, including its ownership, permissions,
symlinks and bind mounts. It must be a readable, root-owned regular file, as
required by vsftpd. A private runtime file is generated atomically on every
start, including when no `CONF_` variables are present. Removing a variable when
recreating the container restores the value from the source config. An option
absent from the source falls back to the legacy environment settings where
applicable (for example, `MIN_PORT`), or to vsftpd's default. For example, source
`max_clients=20`, then `CONF_max_clients=10`, then removing that variable produces
`20`, `10`, `20` across those starts. Runtime files from previous starts are never
used as the source. Custom commands passed to the container bypass generation.
The runtime directory `/var/run/vsftpd` must permit creating and renaming files.
Mount custom configuration at the source path rather than the generated path.

To supply your own config, mount it at the existing source path (read-only is
supported, with or without overrides):

```sh
-v "$PWD/vsftpd.conf:/etc/vsftpd/vsftpd.conf:ro" \
-e CONF_FTPD_BANNER='My FTP server'
```

The effective configuration is a snapshot taken at startup. Restart the container
to read edits to the source file; recreate it to apply environment changes.
Unlike that version, sending `SIGHUP` to vsftpd rereads the generated runtime file and
does not regenerate it from the source. Change any source-edit-and-SIGHUP
automation to restart the container after editing the source.

## USERS examples

- `user|password foo|bar|/home/foo`
- `user|password|/home/user/dir|10000`
- `user|password|/home/user/dir|10000|10000`
- `user|password||10000`
- `user|password||10000|82` : add to an existing group (www-data)
- `user|password|||82` : allocate a UID and use an existing group (www-data)

New home directories use permissions `0750`. Existing home directories keep
their configured permission bits, including mounted directories and symlink
targets. The home directory owner/group is assigned to the configured account;
existing nested file ownership and permissions are not changed recursively.
A regular file or dangling symlink used as a home path is rejected at startup.

## FTPS (File Transfer Protocol + SSL) Example

Issue free Let's Encrypt certificate and use it with `alpine-ftp-server`.

```
mkdir -p /etc/letsencrypt
docker run -it --rm \
    -p 80:80 \
    -v "/etc/letsencrypt:/etc/letsencrypt" \
    certbot/certbot certonly \
    --standalone \
    --preferred-challenges http \
    -n --agree-tos \
    --email i@delfer.ru \
    -d ftp.site.domain
docker run -d \
    --name ftp \
    -p "21:21" \
    -p 21000-21010:21000-21010 \
    -v "/etc/letsencrypt:/etc/letsencrypt:ro" \
    -e USERS="one|1234" \
    -e ADDRESS=ftp.site.domain \
    -e TLS_CERT="/etc/letsencrypt/live/ftp.site.domain/fullchain.pem" \
    -e TLS_KEY="/etc/letsencrypt/live/ftp.site.domain/privkey.pem" \
    delfer/alpine-ftp-server
```

- Do not forget to replace ftp.site.domain with actual domain pointing to your server's IP.
- Be sure you have avalible port 80 for standalone mode of certbot to issue certificate.
- Do not forget to renew certificate in 3 month with `certbot renew` command.

## Via docker-compose
```
alpine-ftp-server:
  image: delfer/alpine-ftp-server
  ports:
    - "21:21"
    - 21000-21010:21000-21010
  environment:
    - USERS="one|1234"
    - ADDRESS=ftp.site.domain
  volumes:
    - ...
```
- If translating the docker run commands to docker-compose files (which uses YAML format), note that YAML parses numbers in
  the format xx:yy as a base-60 value if the number is less than 60, so 21:21 must be specified as a quoted string
