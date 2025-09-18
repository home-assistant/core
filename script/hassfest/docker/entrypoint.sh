#!/bin/sh

integrations=""
integration_path=""
core_path_provided=false

for arg in "$@"; do
    case "$arg" in
        --core-path=*) 
            core_path_provided=true
            break
            ;;
    esac
done

if [ "$core_path_provided" = false ]; then
    # Enable recursive globbing using find
    for manifest in $(find . -name "manifest.json"); do
        manifest_path=$(realpath "${manifest}")
        integrations="$integrations --integration-path ${manifest_path%/*}"
    done

    if [ -z "$integrations" ]; then
        echo "Error: No integrations found!"
        exit 1
    fi
fi

cd /usr/src/homeassistant || exit 1
exec python3 -m script.hassfest --action validate $integrations "$@"
