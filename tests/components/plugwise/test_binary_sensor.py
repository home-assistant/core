"""Tests for the Plugwise binary_sensor integration."""

from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry


async def test_anna_climate_binary_sensor_entities(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related binary_sensor entities."""

    state = hass.states.get("binary_sensor.opentherm_secondary_boiler_state")
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.opentherm_heating")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.opentherm_cooling_enabled")
    assert state
    assert state.state == STATE_OFF


async def test_anna_climate_binary_sensor_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test change of climate related binary_sensor entities."""
    hass.states.async_set("binary_sensor.opentherm_dhw_state", STATE_ON, {})
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_ON

    await async_update_entity(hass, "binary_sensor.opentherm_dhw_state")

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_OFF


async def test_adam_climate_binary_sensor_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test change of climate related binary_sensor entities."""
    state = hass.states.get("binary_sensor.adam_plugwise_notification")
    assert state
    assert state.state == STATE_ON
    assert "warning_msg" in state.attributes
    assert "unreachable" in state.attributes["warning_msg"][0]
    assert not state.attributes.get("error_msg")
    assert not state.attributes.get("other_msg")
