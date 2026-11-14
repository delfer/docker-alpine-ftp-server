#!/bin/sh
# Apply explicit CONF_<option> values without interpreting them as shell/sed code.
set -eu

if [ "$#" -gt 1 ]; then
  printf '%s\n' 'Usage: update_conf.sh [configuration-file]' >&2
  exit 1
fi
config=${1:-/etc/vsftpd/vsftpd.conf}

# Leave existing deployments (including read-only configs) completely untouched
# when no overrides were requested. Read ENVIRON, not newline-delimited env output.
requested=$(awk 'BEGIN { for (name in ENVIRON) if (name ~ /^CONF_/) { print 1; exit } }')
[ -n "$requested" ] || exit 0

if [ ! -f "$config" ] || [ ! -w "$config" ]; then
  printf '%s\n' 'update_conf: configuration must be an existing writable file' >&2
  exit 1
fi

umask 077
temporary=$(mktemp)
trap 'rm -f "$temporary"' 0
trap 'exit 1' HUP INT TERM

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

cmp -s "$temporary" "$config" && exit 0
# Preserve ownership, permissions, symlinks and bind-mounted file inodes.
# All validation and rendering has succeeded before the original is opened.
cat "$temporary" > "$config"
