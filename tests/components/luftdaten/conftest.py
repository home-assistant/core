"""Fixtures for Luftdaten tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.luftdaten.const import CONF_SENSOR_ID, DOMAIN
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_SENSOR_ID: 12345, CONF_SHOW_ON_MAP: True},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.luftdaten.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_luftdaten() -> Generator[MagicMock]:
    """Return a mocked Luftdaten client."""
    with (
        patch(
            "homeassistant.components.luftdaten.Luftdaten", autospec=True
        ) as luftdaten_mock,
        patch(
            "homeassistant.components.luftdaten.config_flow.Luftdaten",
            new=luftdaten_mock,
        ),
    ):
        luftdaten = luftdaten_mock.return_value
        luftdaten.validate_sensor.return_value = True
        luftdaten.sensor_id = 12345
        luftdaten.meta = {
            "altitude": 123.456,
            "latitude": 56.789,
            "longitude": 12.345,
            "sensor_id": 12345,
        }
        luftdaten.values = {
            "humidity": 34.70,
            "P1": 8.5,
            "P2": 4.07,
            "pressure_at_sealevel": 103102.13,
            "pressure": 98545.00,
            "temperature": 22.30,
        }
        yield luftdaten


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_luftdaten: MagicMock
) -> MockConfigEntry:
    """Set up the Luftdaten integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
