import json
import pathlib


component_dir = pathlib.Path('homeassistant/components')


def iter_manifests():
    manifests = [
        json.loads(fil.read_text())
        for fil in component_dir.glob('*/manifest.json')
    ]
    return sorted(manifests, key=lambda man: man['domain'])
