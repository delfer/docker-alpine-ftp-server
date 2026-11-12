#!/bin/sh

#Remove all ftp users
grep '/ftp/' /etc/passwd | cut -d':' -f1 | xargs -r -n1 deluser

#Create users
#USERS='name1|password1|[folder1][|uid1][|gid1] name2|password2|[folder2][|uid2][|gid2]'
#may be:
# user|password foo|bar|/home/foo
#OR
# user|password|/home/user/dir|10000
#OR
# user|password|/home/user/dir|10000|10000
#OR
# user|password||10000|82

#Default user 'ftp' with password 'alpineftp'

if [ -z "$USERS" ]; then
  USERS="alpineftp|alpineftp"
fi

for i in $USERS ; do
  UID_OPT=
  GROUP_OPT=
  NAME=$(echo $i | cut -d'|' -f1)
  GROUP=$NAME
  PASS=$(echo $i | cut -d'|' -f2)
  FOLDER=$(echo $i | cut -d'|' -f3)
  UID=$(echo $i | cut -d'|' -f4)
  # Add group handling
  GID=$(echo $i | cut -d'|' -f5)

  if [ -z "$FOLDER" ]; then
    FOLDER="/ftp/$NAME"
  fi

  if { [ -e "$FOLDER" ] || [ -L "$FOLDER" ]; } && [ ! -d "$FOLDER" ]; then
    printf '%s\n' "Home path must be a directory: $FOLDER" >&2
    exit 1
  fi

  if [ -n "$UID" ]; then
    UID_OPT="-u $UID"
    if [ -z "$GID" ]; then
      GID=$UID
    fi
  fi

  if [ -n "$GID" ]; then
    GROUP=$(getent group "$GID" | cut -d: -f1)
    if [ -z "$GROUP" ]; then
      addgroup -g "$GID" "$NAME"
      GROUP=$NAME
    fi
    GROUP_OPT="-G $GROUP"
  fi

  # BusyBox adduser also chmods pre-existing homes. Preserve mount/custom modes;
  # new homes must be private even when adduser creates them before mkdir.
  FOLDER_MODE=750
  if [ -d "$FOLDER" ]; then
    FOLDER_MODE=$(stat -L -c '%a' "$FOLDER") || exit 1
  fi

  echo -e "$PASS\n$PASS" | adduser -h "$FOLDER" -s /sbin/nologin $UID_OPT $GROUP_OPT "$NAME"
  mkdir -p "$FOLDER"
  chown "$NAME:$GROUP" "$FOLDER"
  chmod "$FOLDER_MODE" "$FOLDER"
  unset NAME PASS FOLDER UID GID
done


if [ -z "$MIN_PORT" ]; then
  MIN_PORT=21000
fi

if [ -z "$MAX_PORT" ]; then
  MAX_PORT=21010
fi

if [ ! -z "$ADDRESS" ]; then
  ADDR_OPT="-opasv_address=$ADDRESS"
fi

if [ ! -z "$TLS_CERT" ] || [ ! -z "$TLS_KEY" ]; then
  TLS_OPT="-orsa_cert_file=$TLS_CERT -orsa_private_key_file=$TLS_KEY -ossl_enable=YES -oallow_anon_ssl=NO -oforce_local_data_ssl=YES -oforce_local_logins_ssl=YES -ossl_tlsv1=NO -ossl_sslv2=NO -ossl_sslv3=NO -ossl_ciphers=HIGH"
fi

# Used to run custom commands inside container
if [ ! -z "$1" ]; then
  exec "$@"
else
  vsftpd -opasv_min_port=$MIN_PORT -opasv_max_port=$MAX_PORT $ADDR_OPT $TLS_OPT /etc/vsftpd/vsftpd.conf || exit $?
  mkdir -p /var/run/vsftpd || exit 1
  # The listener predates its session workers. Exact matching excludes this
  # script and short-lived pipeline children that inherit its process name.
  DAEMON_PID=$(pgrep -xo vsftpd) || exit 1
  printf '%s\n' "$DAEMON_PID" > /var/run/vsftpd/vsftpd.pid || exit 1
  exec pidproxy /var/run/vsftpd/vsftpd.pid true
fi
