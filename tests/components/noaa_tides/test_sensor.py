"""Tests for the NOAA Tides sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from noaa_coops.station import COOPSAPIError
import pandas as pd
import pytest
import requests

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

ENTITY_ID = "sensor.noaa_tides"

YAML_CONFIG = {SENSOR_DOMAIN: {"platform": "noaa_tides", "station_id": "9414290"}}

PREDICTIONS = pd.DataFrame(
    {"type": ["H", "L", "H"], "v": [1.5, 0.2, 1.7]},
    index=pd.to_datetime(["2026-10-26 13:05", "2026-10-26 19:20", "2026-10-27 01:40"]),
)


@pytest.fixture
def mock_station() -> Generator[MagicMock]:
    """Mock the NOAA CO-OPS station."""
    with patch(
        "homeassistant.components.noaa_tides.sensor.coops.Station"
    ) as mock_station_cls:
        yield mock_station_cls.return_value


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            COOPSAPIError("CO-OPS API returned an error. Status Code: 504"),
            id="api_error",
        ),
        pytest.param(requests.exceptions.ConnectionError(), id="connection_error"),
    ],
)
async def test_update_error_marks_unavailable(
    hass: HomeAssistant,
    mock_station: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test the sensor becomes unavailable on API errors and recovers."""
    mock_station.get_data.side_effect = error
    assert await async_setup_component(hass, SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert "Update for sensor.noaa_tides fails" not in caplog.text

    await async_update_entity(hass, ENTITY_ID)
    assert caplog.text.count("NOAA Tides and Currents API is unavailable") == 1

    mock_station.get_data.side_effect = None
    mock_station.get_data.return_value = PREDICTIONS
    await async_update_entity(hass, ENTITY_ID)

    assert hass.states.get(ENTITY_ID).state == "High tide at 1:05 PM"
