"""Tests for the Plugwise Climate integration."""

from plugwise.exceptions import PlugwiseException
import pytest

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from tests.components.plugwise.common import async_init_integration


async def test_adam_climate_entity_attributes(hass, mock_smile_adam):
    """Test creation of adam climate device environment."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes

    assert attrs["hvac_modes"] == [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO]

    assert "preset_modes" in attrs
    assert "no_frost" in attrs["preset_modes"]
    assert "home" in attrs["preset_modes"]

    assert attrs["current_temperature"] == 20.9
    assert attrs["temperature"] == 21.5

    assert attrs["preset_mode"] == "home"

    assert attrs["supported_features"] == 17

    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes

    assert attrs["hvac_modes"] == [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO]

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
    assert entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
            blocking=True,
        )
    state = hass.states.get("climate.zone_lisa_wk")
    attrs = state.attributes
    assert attrs["temperature"] == 21.5

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {"entity_id": "climate.zone_thermostat_jessie", "preset_mode": "home"},
            blocking=True,
        )
    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes
    assert attrs["preset_mode"] == "asleep"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": "climate.zone_thermostat_jessie",
                "hvac_mode": HVAC_MODE_AUTO,
            },
            blocking=True,
        )
    state = hass.states.get("climate.zone_thermostat_jessie")
    attrs = state.attributes


async def test_adam_climate_entity_climate_changes(hass, mock_smile_adam):
    """Test handling of user requests in adam climate device environment."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
        blocking=True,
    )

    assert mock_smile_adam.set_temperature.call_count == 1
    mock_smile_adam.set_temperature.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", 25.0
    )

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_lisa_wk", "preset_mode": "away"},
        blocking=True,
    )

    assert mock_smile_adam.set_preset.call_count == 1
    mock_smile_adam.set_preset.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", "away"
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_thermostat_jessie", "temperature": 25},
        blocking=True,
    )

    assert mock_smile_adam.set_temperature.call_count == 2
    mock_smile_adam.set_temperature.assert_called_with(
        "82fa13f017d240daa0d0ea1775420f24", 25.0
    )

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_thermostat_jessie", "preset_mode": "home"},
        blocking=True,
    )

    assert mock_smile_adam.set_preset.call_count == 2
    mock_smile_adam.set_preset.assert_called_with(
        "82fa13f017d240daa0d0ea1775420f24", "home"
    )


async def test_anna_climate_entity_attributes(hass, mock_smile_anna):
    """Test creation of anna climate device environment."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("climate.anna")
    attrs = state.attributes

    assert "hvac_modes" in attrs
    assert attrs["hvac_modes"] == [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_COOL]

    assert "preset_modes" in attrs
    assert "no_frost" in attrs["preset_modes"]
    assert "home" in attrs["preset_modes"]

    assert attrs["current_temperature"] == 19.3
    assert attrs["temperature"] == 21.0

    assert state.state == HVAC_MODE_HEAT
    assert attrs["hvac_action"] == "heating"
    assert attrs["preset_mode"] == "home"

    assert attrs["supported_features"] == 17


async def test_anna_climate_entity_climate_changes(hass, mock_smile_anna):
    """Test handling of user requests in anna climate device environment."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.anna", "temperature": 25},
        blocking=True,
    )

    assert mock_smile_anna.set_temperature.call_count == 1
    mock_smile_anna.set_temperature.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", 25.0
    )

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.anna", "preset_mode": "away"},
        blocking=True,
    )

    assert mock_smile_anna.set_preset.call_count == 1
    mock_smile_anna.set_preset.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", "away"
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.anna", "hvac_mode": "heat_cool"},
        blocking=True,
    )

    assert mock_smile_anna.set_temperature.call_count == 1
    assert mock_smile_anna.set_schedule_state.call_count == 1
    mock_smile_anna.set_schedule_state.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", None, "false"
    )

    # Auto mode is not available, no schedules
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": "climate.anna", "hvac_mode": "auto"},
            blocking=True,
        )

    assert mock_smile_anna.set_temperature.call_count == 1
    assert mock_smile_anna.set_schedule_state.call_count == 1
