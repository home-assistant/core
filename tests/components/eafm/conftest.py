"""eafm fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.eafm.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_get_stations() -> Generator[AsyncMock]:
    """Mock aioeafm.get_stations."""
    with patch("homeassistant.components.eafm.config_flow.get_stations") as patched:
        patched.return_value = [
            {"label": "My station", "stationReference": "L12345", "RLOIid": "R12345"}
        ]
        yield patched


@pytest.fixture
def mock_get_station(initial_value: dict[str, Any]) -> Generator[AsyncMock]:
    """Mock aioeafm.get_station."""
    with patch("homeassistant.components.eafm.coordinator.get_station") as patched:
        patched.return_value = initial_value
        yield patched


@pytest.fixture
def initial_value() -> dict[str, Any]:
    """Mock aioeafm.get_station."""
    return {
        "label": "My station",
        "measures": [
            {
                "@id": "really-long-unique-id",
                "label": "York Viking Recorder - level-stage-i-15_min----",
                "qualifier": "Stage",
                "parameterName": "Water Level",
                "latestReading": {"value": 5},
                "stationReference": "L1234",
                "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                "unitName": "m",
            }
        ],
    }


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a dummy config entry for testing."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id="VikingRecorder1234",
        data={"station": "L1234"},
        title="Viking Recorder",
    )
    entry.add_to_hass(hass)
    return entry
