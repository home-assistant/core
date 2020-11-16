"""Tests for the Plugwise binary_sensor integration."""

from homeassistant.config_entries import ENTRY_STATE_LOADED
from homeassistant.const import STATE_OFF, STATE_ON

from tests.components.plugwise.common import async_init_integration


async def test_anna_climate_binary_sensor_entities(hass, mock_smile_anna):
    """Test creation of climate related binary_sensor entities."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("binary_sensor.auxiliary_slave_boiler_state")
    assert str(state.state) == STATE_OFF

    state = hass.states.get("binary_sensor.auxiliary_dhw_state")
    assert str(state.state) == STATE_OFF


async def test_anna_climate_binary_sensor_change(hass, mock_smile_anna):
    """Test change of climate related binary_sensor entities."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ENTRY_STATE_LOADED

    hass.states.async_set("binary_sensor.auxiliary_dhw_state", STATE_ON, {})
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.auxiliary_dhw_state")
    assert str(state.state) == STATE_ON

    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.auxiliary_dhw_state"
    )

    state = hass.states.get("binary_sensor.auxiliary_dhw_state")
    assert str(state.state) == STATE_OFF


async def test_adam_climate_binary_sensor_change(hass, mock_smile_adam):
    """Test change of climate related binary_sensor entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("binary_sensor.adam_plugwise_notification")
    assert str(state.state) == STATE_ON
    assert "unreachable" in state.attributes.get("warning_msg")[0]
    assert not state.attributes.get("error_msg")
    assert not state.attributes.get("other_msg")
