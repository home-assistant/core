"""Shared test utilities for span_panel tests.

Prefer HA core test utilities (tests.common) over local helpers.
"""

import json
from pathlib import Path
from typing import Any


def load_json_object_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON object from a fixture in the local test/fixtures directory."""
    fixture_path = Path(__file__).parent / "fixtures" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]
