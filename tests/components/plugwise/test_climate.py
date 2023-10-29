"""Tests for the Plugwise Climate integration."""
from unittest.mock import MagicMock

from plugwise.exceptions import PlugwiseError
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_adam_climate_entity_attributes(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.zone_lisa_wk")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT, HVACMode.AUTO]
    # hvac_action is not asserted as the fixture is not in line with recent firmware functionality

    assert "preset_modes" in state.attributes
    assert "no_frost" in state.attributes["preset_modes"]
    assert "home" in state.attributes["preset_modes"]

    assert state.attributes["current_temperature"] == 20.9
    assert state.attributes["preset_mode"] == "home"
    assert state.attributes["supported_features"] == 17
    assert state.attributes["temperature"] == 21.5
    assert state.attributes["min_temp"] == 0.0
    assert state.attributes["max_temp"] == 99.9
    assert state.attributes["target_temp_step"] == 0.1

    state = hass.states.get("climate.zone_thermostat_jessie")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT, HVACMode.AUTO]
    # hvac_action is not asserted as the fixture is not in line with recent firmware functionality

    assert "preset_modes" in state.attributes
    assert "no_frost" in state.attributes["preset_modes"]
    assert "home" in state.attributes["preset_modes"]

    assert state.attributes["current_temperature"] == 17.2
    assert state.attributes["preset_mode"] == "asleep"
    assert state.attributes["temperature"] == 15.0
    assert state.attributes["min_temp"] == 0.0
    assert state.attributes["max_temp"] == 99.9
    assert state.attributes["target_temp_step"] == 0.1


async def test_adam_2_climate_entity_attributes(
    hass: HomeAssistant, mock_smile_adam_2: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes["hvac_action"] == "heating"
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT, HVACMode.AUTO]

    state = hass.states.get("climate.lisa_badkamer")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_action"] == "idle"
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT, HVACMode.AUTO]


async def test_adam_3_climate_entity_attributes(
    hass: HomeAssistant, mock_smile_adam_3: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.anna")

    assert state
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes["hvac_action"] == "cooling"
    assert state.attributes["hvac_modes"] == [
        HVACMode.HEAT_COOL,
        HVACMode.AUTO,
    ]


async def test_adam_climate_adjust_negative_testing(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test exceptions of climate entities."""
    mock_smile_adam.set_preset.side_effect = PlugwiseError
    mock_smile_adam.set_schedule_state.side_effect = PlugwiseError
    mock_smile_adam.set_temperature.side_effect = PlugwiseError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {"entity_id": "climate.zone_thermostat_jessie", "preset_mode": "home"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": "climate.zone_thermostat_jessie",
                "hvac_mode": HVACMode.AUTO,
            },
            blocking=True,
        )


async def test_adam_climate_entity_climate_changes(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test handling of user requests in adam climate device environment."""
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_lisa_wk", "temperature": 25},
        blocking=True,
    )

    assert mock_smile_adam.set_temperature.call_count == 1
    mock_smile_adam.set_temperature.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", {"setpoint": 25.0}
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.zone_lisa_wk",
            "hvac_mode": "heat",
            "temperature": 25,
        },
        blocking=True,
    )

    assert mock_smile_adam.set_temperature.call_count == 2
    mock_smile_adam.set_temperature.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", {"setpoint": 25.0}
    )

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.zone_lisa_wk", "temperature": 150},
            blocking=True,
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

    assert mock_smile_adam.set_temperature.call_count == 3
    mock_smile_adam.set_temperature.assert_called_with(
        "82fa13f017d240daa0d0ea1775420f24", {"setpoint": 25.0}
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

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": "climate.zone_thermostat_jessie",
                "hvac_mode": "dry",
            },
            blocking=True,
        )


async def test_anna_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_action"] == "heating"
    assert state.attributes["hvac_modes"] == [
        HVACMode.HEAT,
        HVACMode.AUTO,
    ]

    assert "no_frost" in state.attributes["preset_modes"]
    assert "home" in state.attributes["preset_modes"]

    assert state.attributes["current_temperature"] == 19.3
    assert state.attributes["preset_mode"] == "home"
    assert state.attributes["supported_features"] == 17
    assert state.attributes["temperature"] == 20.5
    assert state.attributes["min_temp"] == 4.0
    assert state.attributes["max_temp"] == 30.0
    assert state.attributes["target_temp_step"] == 0.1


async def test_anna_2_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna_2: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_action"] == "cooling"
    assert state.attributes["hvac_modes"] == [
        HVACMode.HEAT_COOL,
        HVACMode.AUTO,
    ]
    assert state.attributes["supported_features"] == 18
    assert state.attributes["target_temp_high"] == 24.0
    assert state.attributes["target_temp_low"] == 20.5


async def test_anna_3_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna_3: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes["hvac_action"] == "idle"
    assert state.attributes["hvac_modes"] == [
        HVACMode.HEAT_COOL,
        HVACMode.AUTO,
    ]


async def test_anna_climate_entity_climate_changes(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test handling of user requests in anna climate device environment."""
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.anna", "target_temp_high": 25, "target_temp_low": 20},
        blocking=True,
    )

    assert mock_smile_anna.set_temperature.call_count == 1
    mock_smile_anna.set_temperature.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5",
        {"setpoint_high": 25.0, "setpoint_low": 20.0},
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
        {"entity_id": "climate.anna", "hvac_mode": "heat"},
        blocking=True,
    )

    assert mock_smile_anna.set_temperature.call_count == 1
    assert mock_smile_anna.set_schedule_state.call_count == 1
    mock_smile_anna.set_schedule_state.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", "standaard", "off"
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.anna", "hvac_mode": "auto"},
        blocking=True,
    )

    assert mock_smile_anna.set_schedule_state.call_count == 2
    mock_smile_anna.set_schedule_state.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", "standaard", "on"
    )
