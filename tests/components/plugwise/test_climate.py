"""Tests for the Plugwise Climate integration."""

from plugwise.exceptions import PlugwiseException

from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_HEAT
from homeassistant.config_entries import ENTRY_STATE_LOADED

from tests.components.plugwise.common import async_init_integration


async def test_adam_climate_entity_attributes(hass, mock_smile_adam):
    """Test creation of adam climate device environment."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes

    assert attrs["hvac_modes"] == [HVAC_MODE_HEAT, HVAC_MODE_AUTO]

    assert "preset_modes" in attrs
    assert "no_frost" in attrs["preset_modes"]
    assert "home" in attrs["preset_modes"]

    assert attrs["current_temperature"] == 20.9
    assert attrs["temperature"] == 21.5

    assert attrs["preset_mode"] == "home"

    assert attrs["supported_features"] == 17

    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes

    assert attrs["hvac_modes"] == [HVAC_MODE_HEAT, HVAC_MODE_AUTO]

    assert "preset_modes" in attrs
    assert "no_frost" in attrs["preset_modes"]
    assert "home" in attrs["preset_modes"]

    assert attrs["current_temperature"] == 17.2
    assert attrs["temperature"] == 15.0

    assert attrs["preset_mode"] == "asleep"


async def test_adam_climate_adjust_negative_testing(hass, mock_smile_adam):
    """Test exceptions of climate entities."""
    mock_smile_adam.set_preset.side_effect = PlugwiseException
    mock_smile_adam.set_schedule_state.side_effect = PlugwiseException
    mock_smile_adam.set_temperature.side_effect = PlugwiseException
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
        blocking=True,
    )
    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes
    assert attrs["temperature"] == 21.5

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_thermostat_jessie", "preset_mode": "home"},
        blocking=True,
    )
    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes
    assert attrs["preset_mode"] == "asleep"

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.zone_thermostat_jessie", "hvac_mode": HVAC_MODE_AUTO},
        blocking=True,
    )
    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes


async def test_adam_climate_entity_climate_changes(hass, mock_smile_adam):
    """Test handling of user requests in adam climate device environment."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
        blocking=True,
    )
    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes

    assert attrs["temperature"] == 25.0

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_lisa_wk", "preset_mode": "away"},
        blocking=True,
    )
    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes

    assert attrs["preset_mode"] == "away"

    assert attrs["supported_features"] == 17

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_thermostat_jessie", "temperature": 25},
        blocking=True,
    )

    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes

    assert attrs["temperature"] == 25.0

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_thermostat_jessie", "preset_mode": "home"},
        blocking=True,
    )
    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes

    assert attrs["preset_mode"] == "home"


async def test_anna_climate_entity_attributes(hass, mock_smile_anna):
    """Test creation of anna climate device environment."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("climate.anna")
    attrs = state.attributes

    assert "hvac_modes" in attrs
    assert "heat_cool" in attrs["hvac_modes"]

    assert "preset_modes" in attrs
    assert "no_frost" in attrs["preset_modes"]
    assert "home" in attrs["preset_modes"]

    assert attrs["current_temperature"] == 23.3
    assert attrs["temperature"] == 21.0

    assert state.state == HVAC_MODE_AUTO
    assert attrs["hvac_action"] == "idle"
    assert attrs["preset_mode"] == "home"

    assert attrs["supported_features"] == 17


async def test_anna_climate_entity_climate_changes(hass, mock_smile_anna):
    """Test handling of user requests in anna climate device environment."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ENTRY_STATE_LOADED

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.anna", "temperature": 25},
        blocking=True,
    )

    state = hass.states.get("climate.anna")
    attrs = state.attributes

    assert attrs["temperature"] == 25.0

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.anna", "preset_mode": "away"},
        blocking=True,
    )

    state = hass.states.get("climate.anna")
    attrs = state.attributes

    assert attrs["preset_mode"] == "away"

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.anna", "hvac_mode": "heat_cool"},
        blocking=True,
    )

    state = hass.states.get("climate.anna")
    attrs = state.attributes

    assert state.state == "heat_cool"
