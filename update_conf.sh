#!/bin/sh

readonly CONF_FILE_PATH="/etc/vsftpd/vsftpd.conf"

env | grep -E '^CONF_' | grep -Ev '^CONF_FILE_PATH=' | while IFS== read parm value ; do
  parm="${parm#CONF_*}" ;
  parm=`echo "${parm}" | tr 'A-Z' 'a-z'`
  echo "Setting parm ${parm} to ${value}"
  if ( grep -qE "^#?${parm}=" ${CONF_FILE_PATH} ) ; then
    sed -i "s;^#\?${parm}=.*;${parm}=${value};" "${CONF_FILE_PATH}"
  else
    sed -i "$ a\\#\n# Parameter based on environment variable\n${parm}=${value}" "${CONF_FILE_PATH}"
  fi
done
