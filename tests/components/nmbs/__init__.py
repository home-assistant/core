"""Tests for the NMBS integration."""

import json
from typing import Any

from tests.common import load_fixture


def mocked_request_function() -> dict[str, Any]:
    """Mock of the request function."""
    dummy_stations_response: dict[str, Any] = json.loads(
        load_fixture("stations.json", "nmbs")
    )

    return dummy_stations_response
