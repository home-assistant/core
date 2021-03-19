"""The test for the Salus thermostat module."""
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import HTTPError

from homeassistant.components.salus.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.update_coordinator import UpdateFailed

from .mocks import (
    MOCK_CONFIG_ENTRY,
    MOCK_DEVICE_ID,
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


async def test_climate_set_temperature(hass):
    """Test setting a temperature."""
    mock_salus = _get_mock_salus(_get_mock_device_reading_not_heating)
    mock_set_temperature = MagicMock()
    type(mock_salus).set_manual_override = mock_set_temperature

    with patch(
        "homeassistant.components.salus.Api",
        return_value=mock_salus,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        service_data={
            ATTR_ENTITY_ID: "climate.it500_salus_temperature",
            "temperature": 22,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_set_temperature.assert_called_once_with(MOCK_DEVICE_ID, 22)


async def test_climate_set_temperature_on_error(hass):
    """Test setting a temperature."""
    mock_salus = _get_mock_salus()
    mock_set_temperature = MagicMock()
    mock_set_temperature.side_effect = HTTPError(Mock(status=500), "unknown")
    type(mock_salus).set_manual_override = mock_set_temperature

    with patch(
        "homeassistant.components.salus.Api",
        return_value=mock_salus,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(UpdateFailed):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            service_data={
                ATTR_ENTITY_ID: "climate.it500_salus_temperature",
                "temperature": 22,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    mock_set_temperature.assert_called_once_with(MOCK_DEVICE_ID, 22)
