#!/usr/bin/env bashio
declare -a integrations
declare integration_path

shopt -s globstar nullglob
for manifest in **/manifest.json; do
    manifest_path=$(realpath "${manifest}")
    integrations+=(--integration-path "${manifest_path%/*}")
done

if [[ ${#integrations[@]} -eq 0 ]]; then
    bashio::exit.nok "No integrations found!"
fi

cd /usr/src/homeassistant
exec python3 -m script.hassfest --action validate "${integrations[@]}" "$@"