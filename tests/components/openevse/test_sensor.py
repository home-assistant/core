"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry


@pytest.fixture
def mock_charger():
    """Create a mock OpenEVSE charger."""
    with patch("homeassistant.components.openevse.openevsewifi.Charger") as mock:
        charger = MagicMock()
        charger.getStatus.return_value = "Charging"
        charger.getChargeTimeElapsed.return_value = 3600  # 60 minutes in seconds
        charger.getAmbientTemperature.return_value = 25.5
        charger.getIRTemperature.return_value = 30.2
        charger.getRTCTemperature.return_value = 28.7
        charger.getUsageSession.return_value = 15000  # 15 kWh in Wh
        charger.getUsageTotal.return_value = 500000  # 500 kWh in Wh
        charger.charging_current = 32.0
        mock.return_value = charger
        yield charger


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain="openevse",
        data={CONF_HOST: "192.168.1.100"},
        unique_id="192.168.1.100",
    )


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setting up the sensor platform."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Trigger updates for all sensor entities

    for entity_id in hass.states.async_entity_ids(SENSOR_DOMAIN):
        await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.charging_status")
    assert state.state == "Charging"

    state = hass.states.get("sensor.charge_time_elapsed")
    assert state.state == "60.0"

    state = hass.states.get("sensor.ambient_temperature")
    assert state.state == "25.5"

    state = hass.states.get("sensor.usage_this_session")
    assert state.state == "15.0"

    state = hass.states.get("sensor.total_usage")
    assert state.state == "500.0"

    state = hass.states.get("sensor.current_charging_current")
    assert state.state == "32.0"
