#!/bin/sh

readonly CONF_FILE_PATH="/etc/vsftpd/vsftpd.conf"

# Check if config file exists
if [ ! -f "${CONF_FILE_PATH}" ]; then
  echo "Error: Configuration file ${CONF_FILE_PATH} not found"
  exit 1
fi

# Check if config file is writable
if [ ! -w "${CONF_FILE_PATH}" ]; then
  echo "Error: Configuration file ${CONF_FILE_PATH} is not writable"
  exit 1
fi

# Create a temporary file for the final config
TEMP_FILE=$(mktemp)
if [ $? -ne 0 ]; then
  echo "Error: Failed to create temporary file"
  exit 1
fi

# Copy the original config to the temp file
cp "${CONF_FILE_PATH}" "${TEMP_FILE}"
if [ $? -ne 0 ]; then
  echo "Error: Failed to copy configuration file"
  rm -f "${TEMP_FILE}"
  exit 1
fi

# Create a list of parameters to add (those not found in the config)
NEW_PARAMS_FILE=$(mktemp)
if [ $? -ne 0 ]; then
  echo "Error: Failed to create temporary file for new parameters"
  rm -f "${TEMP_FILE}"
  exit 1
fi

# Process environment variables
env | grep -E '^CONF_' | grep -Ev '^CONF_FILE_PATH=' | while IFS== read parm value ; do
  # Extract parameter name (remove CONF_ prefix and convert to lowercase)
  param_name=$(echo "${parm#CONF_}" | tr 'A-Z' 'a-z')
  
  echo "Setting parameter ${param_name} to ${value}"
  
  # Escape special characters in value for sed
  escaped_value=$(echo "$value" | sed 's/[\/&]/\\&/g')
  
  # Check if parameter exists (commented or uncommented)
  if grep -qE "^[[:space:]]*#?[[:space:]]*${param_name}[[:space:]]*=" "${CONF_FILE_PATH}"; then
    # Update existing parameter in the temp file
    sed -i -E "s/^[[:space:]]*#?[[:space:]]*${param_name}[[:space:]]*=.*/${param_name}=${escaped_value}/" "${TEMP_FILE}"
    
    # Check if sed command succeeded
    if [ $? -ne 0 ]; then
      echo "Error: Failed to update parameter ${param_name}"
    fi
  else
    # Add to the list of new parameters
    echo "${param_name}|${value}" >> "${NEW_PARAMS_FILE}"
  fi
done

# Add new parameters to the end of the config file
if [ -s "${NEW_PARAMS_FILE}" ]; then
  echo "" >> "${TEMP_FILE}"
  echo "# Parameters added by environment variables" >> "${TEMP_FILE}"
  
  while IFS="|" read param_name value; do
    echo "${param_name}=${value}" >> "${TEMP_FILE}"
  done < "${NEW_PARAMS_FILE}"
fi

# Replace the original file with the updated one
cat "${TEMP_FILE}" > "${CONF_FILE_PATH}"

# Clean up
rm -f "${TEMP_FILE}" "${NEW_PARAMS_FILE}"
