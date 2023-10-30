# docker-alpine-ftp-server
[![Docker Stars](https://img.shields.io/docker/stars/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Pulls](https://img.shields.io/docker/pulls/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Automated build](https://img.shields.io/docker/automated/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![Docker Build Status](https://img.shields.io/docker/build/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![MicroBadger Layers](https://img.shields.io/microbadger/layers/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/) [![MicroBadger Size](https://img.shields.io/microbadger/image-size/delfer/alpine-ftp-server.svg)](https://hub.docker.com/r/delfer/alpine-ftp-server/)  
Small and flexible docker image with vsftpd server

## Usage
```
docker run -d \
    -p 21:21 \
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
- `CONF_FTPD_BANNER` - custom banner (default `Welcome Alpine ftp server https://hub.docker.com/r/delfer/alpine-ftp-server/`)
- `CONF_COMMENT_PARMS` - comment a parm if existing in the vsftp.conf file
  - format `parm1,parm2`
- `CONF_UNCOMMENT_PARMS` - uncomment a parm if existing in the vsftp.conf file
  - format `parm1,parm2`
- `CONF_SET_PARMS` - set specific parameters in the vsftp.conf file - overwrite existing ones
  - format `parm1=value1,parm2=value2`

## USERS examples

- `user|password foo|bar|/home/foo`
- `user|password|/home/user/dir|10000`
- `user|password|/home/user/dir|10000|10000`
- `user|password||10000`
- `user|password||10000|82` : add to an existing group (www-data)

## CONF examples

- `CONF_FTPD_BANNER`: `My ftps server`
- `CONF_COMMENT_PARMS`: `pasv_enable,pasv_addr_resolve`
- `CONF_UNCOMMENT_PARMS`: `chroot_local_user,chroot_list_enable,chroot_list_file`
- `CONF_SET_PARMS`: `chroot_local_user=YES,chroot_list_enable=YES,allow_writeable_chroot=YES,chroot_list_file=/etc/vsftpd.chroot_list,max_login_fails=3,max_per_ip=3,max_clients=10`

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
    -p 21:21 \
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

## FTPS Example with docker compose

### docker-compose.yml file

```
services:
  ftps:
    image: delfer/alpine-ftp-server
    environment:
      - CONF_FTPD_BANNER=My ftps server
      - CONF_SET_PARMS=chroot_local_user=YES,chroot_list_enable=YES,allow_writeable_chroot=YES,chroot_list_file=/etc/vsftpd.chroot_list,max_login_fails=3,max_per_ip=3,max_clients=10
      - USERS=user1|password1 user2|password2
      - ADDRESS=ftp.site.domain
      - TLS_CERT=/etc/letsencrypt/live/ftp.site.domain/fullchain.pem
      - TLS_KEY=/etc/letsencrypt/live/ftp.site.domain/privkey.pem
    cap_add:
      - CAP_NET_BIND_SERVICE
    deploy:
      replicas: 1
    expose:
      - "21"
      - "21000-21010:21000-21010"
    ports:
      - "21:21"
      - "21000-21010:21000-21010"
    volumes:
      - ftps_ftp:/ftp
      - $PWD/vsftpd.chroot_list:/etc/vsftpd.chroot_list
      - /letsencrypt/live/ftps.acme.com:/etc/letsencrypt/live/ftps.acme.com:ro
volumes:
    ftps_ftp:
```

### Run from the docker-compose.yml directory
```
mkdir -p /etc/letsencrypt
docker run -it --rm \
    -p 80:80 \
    -v "/etc/letsencrypt:/etc/letsencrypt" \
    certbot/certbot certonly \
    --standalone \
    --preferred-challenges http \
    -n --agree-tos \
    --email i@delfer.ru 
    -d ftp.site.domain
touch vsftpd.chroot_list
docker compose -d
```
