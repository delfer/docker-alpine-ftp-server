# docker-alpine-ftp-server
[![Docker Stars](https://img.shields.io/docker/stars/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Pulls](https://img.shields.io/docker/pulls/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Automated build](https://img.shields.io/docker/automated/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Build Status](https://img.shields.io/docker/build/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![MicroBadger Layers](https://img.shields.io/microbadger/layers/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![MicroBadger Size](https://img.shields.io/microbadger/image-size/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/)  
Small and flexible docker image with vsftpd server

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

## USERS examples

- `user|password foo|bar|/home/foo`
- `user|password|/home/user/dir|10000`
- `user|password|/home/user/dir|10000|10000`
- `user|password||10000`
- `user|password||10000|82` : add to an existing group (www-data)

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
