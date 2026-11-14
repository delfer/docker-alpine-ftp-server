#!/bin/sh
# Apply explicit CONF_<option> values without interpreting them as shell/sed code.
set -eu

if [ "$#" -gt 2 ]; then
  printf '%s\n' 'Usage: update_conf.sh [source-config [runtime-config]]' >&2
  exit 1
fi
config=${1:-/etc/vsftpd/vsftpd.conf}
output=${2:-/var/run/vsftpd/vsftpd.conf}

if [ ! -f "$config" ] || [ ! -r "$config" ]; then
  printf '%s\n' 'update_conf: source configuration must be an existing readable file' >&2
  exit 1
fi
# Copying into a root-owned runtime file must not bypass vsftpd's source-owner
# check. Follow symlinks just as vsftpd does when opening the source.
if [ "$(stat -L -c '%u' "$config")" != 0 ]; then
  printf '%s\n' 'update_conf: source configuration must be owned by root' >&2
  exit 1
fi
if [ "$config" -ef "$output" ] || [ -d "$output" ]; then
  printf '%s\n' 'update_conf: runtime configuration must be a separate file' >&2
  exit 1
fi

umask 077
mkdir -p "$(dirname "$output")"
# Stage beside the destination so publication is an atomic rename, including
# when /tmp and /var/run are on different filesystems.
temporary=$(mktemp "$output.tmp.XXXXXX")
trap 'rm -f "$temporary"' 0
trap 'exit 1' HUP INT TERM

# Read ENVIRON, not newline-delimited env output. With no overrides, retain the
# exact source bytes. Always rebuild from the source, never a prior generation.
requested=$(awk 'BEGIN { for (name in ENVIRON) if (name ~ /^CONF_/) { print 1; exit } }')
if [ -z "$requested" ]; then
  cat "$config" > "$temporary"
else
LC_ALL=C awk '
function fail(message) {
  print "update_conf: " message > "/dev/stderr"
  failed = 1
  exit 1
}
BEGIN {
  for (name in ENVIRON) {
    if (name !~ /^CONF_/) continue
    key = substr(name, 6)
    if (key !~ /^[A-Za-z][A-Za-z0-9_]*$/)
      fail("invalid CONF_ parameter name")
    key = tolower(key)
    value = ENVIRON[name]
    if (value ~ /[\r\n]/)
      fail("multiline value for " key)
    if (key in values) {
      if (("x" values[key]) != ("x" value))
        fail("conflicting CONF_ variables for " key)
    } else {
      keys[++count] = key
    }
    values[key] = value
  }
}
{
  key = $0
  sub(/^[ \t]*#?[ \t]*/, "", key)
  sub(/[ \t]*=.*/, "", key)
  key = tolower(key)
  if (index($0, "=") && key in values) {
    # A single canonical assignment replaces all active/commented duplicates.
    if (!seen[key]++) print key "=" values[key]
  } else {
    print
  }
}
END {
  if (failed) exit 1
  # Keep newly appended options in a predictable order on every awk variant.
  for (i = 1; i <= count; i++)
    for (j = i + 1; j <= count; j++)
      if (keys[i] > keys[j]) {
        key = keys[i]; keys[i] = keys[j]; keys[j] = key
      }
  for (i = 1; i <= count; i++) {
    key = keys[i]
    if (!seen[key]) print key "=" values[key]
  }
}
' < "$config" > "$temporary"
fi

if mv -f "$temporary" "$output"; then
  exit 0
else
  status=$?
  printf '%s\n' 'update_conf: failed to publish runtime configuration' >&2
  exit "$status"
fi
