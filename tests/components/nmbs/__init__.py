"""Tests for the NMBS integration."""

import json
from typing import Any

from tests.common import load_fixture


def mock_api_unavailable() -> dict[str, Any]:
    """Mock for unavailable api."""
    return -1


def mock_station_response() -> dict[str, Any]:
    """Mock for valid station response."""
    dummy_stations_response: dict[str, Any] = json.loads(
        load_fixture("stations.json", "nmbs")
    )

    return dummy_stations_response
