"""Helpers to deal with manifests."""
import json
import pathlib

component_dir = pathlib.Path("homeassistant/components")


def iter_manifests():
    """Iterate over all available manifests."""
    manifests = [
        json.loads(fil.read_text()) for fil in component_dir.glob("*/manifest.json")
    ]
    return sorted(manifests, key=lambda man: man["domain"])
