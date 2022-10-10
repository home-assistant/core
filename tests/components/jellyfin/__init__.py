"""Tests for the jellyfin integration."""
import json
from typing import Any

from tests.common import load_fixture


def load_json_fixture(filename: str) -> Any:
    """Load JSON fixture on-demand."""
    return json.loads(load_fixture(f"jellyfin/{filename}"))
