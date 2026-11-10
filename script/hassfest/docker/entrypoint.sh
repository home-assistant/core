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
    # Manifest discovery is limited to the two documented custom-integration
    # locations rather than anywhere in the repo, to avoid misvalidating
    # unrelated files that happen to share the filename.
    manifests=$(
        { [ -d custom_components ] && find custom_components -mindepth 2 -maxdepth 2 -name "manifest.json"
          find . -maxdepth 1 -name "manifest.json"; } 2>/dev/null
    )

    for manifest in $manifests; do
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
