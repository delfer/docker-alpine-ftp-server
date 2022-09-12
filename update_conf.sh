#!/bin/sh

readonly CONF_FILE="/etc/vsftpd/vsftpd.conf"

if [ ! -z "${CONF_FTPD_BANNER}" ] ; then
  sed -i "/^ftpd_banner/ s/.*/ftpd_banner=${CONF_FTPD_BANNER}/" "${CONF_FILE}"
fi

OIFS=$IFS
IFS=,
if [ ! -z "${CONF_UNCOMMENT_PARMS}" ] ; then
  for parm in ${CONF_UNCOMMENT_PARMS} ; do
    echo "Uncommenting parm $parm"
    sed -i "s/^#\(${parm}=\)/\\1/" "${CONF_FILE}"
  done
fi

if [ ! -z "${CONF_COMMENT_PARMS}" ] ; then
  for parm in ${CONF_COMMENT_PARMS} ; do
    echo "Commenting parm $parm"
    sed -i "s/^\(${parm}=\)/#\\1/" "${CONF_FILE}"
  done
fi

if [ ! -z "${CONF_SET_PARMS}" ] ; then
  for parm in ${CONF_SET_PARMS} ; do
    echo $parm | while IFS== read var val ; do
      echo "Setting parm $parm"
      if ( grep -qE "^#?${var}=" ${CONF_FILE} ) ; then
        sed -i "s;^#\?${var}=.*;${parm};" "${CONF_FILE}"
      else
        sed -i "$ a\\\n${parm}" "${CONF_FILE}"
      fi
    done
  done
fi
IFS=$OIFS

