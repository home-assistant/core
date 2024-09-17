#!/bin/sh

integrations=""
integration_path=""

# Enable recursive globbing using find
for manifest in $(find . -name "manifest.json"); do
    manifest_path=$(realpath "${manifest}")
    integrations="$integrations --integration-path ${manifest_path%/*}"
done

if [ -z "$integrations" ]; then
    echo "Error: No integrations found!"
    exit 1
fi

cd /usr/src/homeassistant || exit 1
exec python3 -m script.hassfest --action validate $integrations "$@"
