"""Shared translation data loading."""

import json
from pathlib import Path
from typing import Any


class JSONDecodeErrorWithPath(json.JSONDecodeError):
    """Subclass of JSONDecodeError with additional properties.

    Additional properties:
      path: Path to the JSON document being parsed
    """

    def __init__(self, msg, doc, pos, path):
        """Initialize."""
        lineno = doc.count("\n", 0, pos) + 1
        colno = pos - doc.rfind("\n", 0, pos)
        errmsg = f"{msg}: file: {path} line {lineno} column {colno} (char {pos})"
        ValueError.__init__(self, errmsg)
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = lineno
        self.colno = colno
        self.path = path

    def __reduce__(self):
        """Reduce."""
        return self.__class__, (self.msg, self.doc, self.pos, self.path)


def load_json_from_path(path: Path) -> Any:
    """Load JSON from path."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise JSONDecodeErrorWithPath(err.msg, err.doc, err.pos, path) from err


def generate_upload_data(core_path: Path) -> dict[str, Any]:
    """Collect Core and integration translation strings."""
    integrations_dir = core_path / "homeassistant/components"
    translations = load_json_from_path(integrations_dir.parent / "strings.json")
    translations["component"] = {
        path.parent.name: load_json_from_path(path)
        for path in integrations_dir.glob("*/strings.json")
    }
    return translations
