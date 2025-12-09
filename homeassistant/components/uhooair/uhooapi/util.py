"""Imports for util.py."""

import json
from typing import Any


def json_pp(obj: Any) -> str:
    """Format json object."""
    return json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "))
