"""The test for the NuHeat thermostat module."""
from unittest.mock import patch

from homeassistant.components.salus.const import DOMAIN

from .mocks import (
    MOCK_CONFIG_ENTRY,
    _get_mock_device_reading_not_heating,
    _get_mock_salus,
)

from tests.common import MockConfigEntry


async def test_climate_thermostat_run(hass):
    """Test a thermostat with the schedule running."""
    mock_salus = _get_mock_salus()

    with patch(
        "homeassistant.components.salus.Api",
        return_value=mock_salus,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.it500_salus_temperature")
    assert state.state == "heat"
    expected_attributes = {
        "hvac_modes": ["heat"],
        "min_temp": 7,
        "max_temp": 35,
        "hvac_action": "heating",
        "current_temperature": 21.5,
        "temperature": 23.5,
        "friendly_name": "IT500 Salus Temperature",
        "supported_features": 1,
    }

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_climate_thermostat_not_heating(hass):
    """Test a thermostat with the schedule not running."""
    mock_salus = _get_mock_salus(_get_mock_device_reading_not_heating)

    with patch(
        "homeassistant.components.salus.Api",
        return_value=mock_salus,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.it500_salus_temperature")
    print(state.attributes.items())
    assert state.state == "off"
    expected_attributes = {
        "hvac_modes": ["heat"],
        "min_temp": 7,
        "max_temp": 35,
        "hvac_action": "idle",
        "current_temperature": 23,
        "temperature": 22.5,
        "friendly_name": "IT500 Salus Temperature",
        "supported_features": 1,
    }

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())
