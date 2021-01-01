"""The test for the NuHeat thermostat module."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.nuheat.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .mocks import (
    _get_mock_nuheat,
    _get_mock_thermostat_run,
    _get_mock_thermostat_schedule_hold_available,
    _get_mock_thermostat_schedule_hold_unavailable,
    _get_mock_thermostat_schedule_temporary_hold,
    _mock_get_config,
)

from tests.common import async_fire_time_changed


async def test_climate_thermostat_run(hass):
    """Test a thermostat with the schedule running."""
    mock_thermostat = _get_mock_thermostat_run()
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
        await hass.async_block_till_done()

    state = hass.states.get("climate.master_bathroom")
    assert state.state == "auto"
    expected_attributes = {
        "current_temperature": 22.2,
        "friendly_name": "Master bathroom",
        "hvac_action": "heating",
        "hvac_modes": ["auto", "heat"],
        "max_temp": 69.4,
        "min_temp": 5.0,
        "preset_mode": "Run Schedule",
        "preset_modes": ["Run Schedule", "Temporary Hold", "Permanent Hold"],
        "supported_features": 17,
        "temperature": 22.2,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_climate_thermostat_schedule_hold_unavailable(hass):
    """Test a thermostat with the schedule hold that is offline."""
    mock_thermostat = _get_mock_thermostat_schedule_hold_unavailable()
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
        await hass.async_block_till_done()

    state = hass.states.get("climate.guest_bathroom")

    assert state.state == "unavailable"
    expected_attributes = {
        "friendly_name": "Guest bathroom",
        "hvac_modes": ["auto", "heat"],
        "max_temp": 180.6,
        "min_temp": -6.1,
        "preset_modes": ["Run Schedule", "Temporary Hold", "Permanent Hold"],
        "supported_features": 17,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_climate_thermostat_schedule_hold_available(hass):
    """Test a thermostat with the schedule hold that is online."""
    mock_thermostat = _get_mock_thermostat_schedule_hold_available()
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
        await hass.async_block_till_done()

    state = hass.states.get("climate.available_bathroom")

    assert state.state == "auto"
    expected_attributes = {
        "current_temperature": 38.9,
        "friendly_name": "Available bathroom",
        "hvac_action": "idle",
        "hvac_modes": ["auto", "heat"],
        "max_temp": 180.6,
        "min_temp": -6.1,
        "preset_mode": "Run Schedule",
        "preset_modes": ["Run Schedule", "Temporary Hold", "Permanent Hold"],
        "supported_features": 17,
        "temperature": 26.1,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_climate_thermostat_schedule_temporary_hold(hass):
    """Test a thermostat with the temporary schedule hold that is online."""
    mock_thermostat = _get_mock_thermostat_schedule_temporary_hold()
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
        await hass.async_block_till_done()

    state = hass.states.get("climate.temp_bathroom")

    assert state.state == "auto"
    expected_attributes = {
        "current_temperature": 94.4,
        "friendly_name": "Temp bathroom",
        "hvac_action": "idle",
        "hvac_modes": ["auto", "heat"],
        "max_temp": 180.6,
        "min_temp": -0.6,
        "preset_mode": "Run Schedule",
        "preset_modes": ["Run Schedule", "Temporary Hold", "Permanent Hold"],
        "supported_features": 17,
        "temperature": 37.2,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    await hass.services.async_call(
        "climate",
        "set_temperature",
        service_data={ATTR_ENTITY_ID: "climate.temp_bathroom", "temperature": 90},
        blocking=True,
    )
    await hass.async_block_till_done()

    # opportunistic set
    state = hass.states.get("climate.temp_bathroom")
    assert state.attributes["preset_mode"] == "Temporary Hold"
    assert state.attributes["temperature"] == 50.0

    # and the api poll returns it to the mock
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    state = hass.states.get("climate.temp_bathroom")
    assert state.attributes["preset_mode"] == "Run Schedule"
    assert state.attributes["temperature"] == 37.2
