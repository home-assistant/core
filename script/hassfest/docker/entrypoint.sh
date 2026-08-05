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
    # Only look for manifest.json in the locations Home Assistant and HACS
    # actually document as valid for custom integrations:
    #   - custom_components/<domain>/manifest.json (standard layout)
    #   - ./manifest.json (HACS "content_in_root" layout)
    # A repo-wide recursive find picks up unrelated manifest.json files that
    # happen to share the filename (e.g. browser-extension manifests bundled
    # alongside the integration), which are not Home Assistant manifests and
    # cause confusing crashes when hassfest tries to validate them as such.
    if [ -d custom_components ]; then
        manifests=$(find custom_components -maxdepth 2 -name "manifest.json")
    else
        manifests=$(find . -maxdepth 1 -name "manifest.json")
    fi

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
