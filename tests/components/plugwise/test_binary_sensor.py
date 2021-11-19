"""Tests for the Plugwise binary_sensor integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity_registry import async_get_registry

from tests.components.plugwise.common import async_init_integration


async def test_anna_climate_binary_sensor_entities(hass, mock_smile_anna):
    """Test creation of climate related binary_sensor entities."""
    a_sensor = "binary_sensor.auxiliary_slave_boiler_state"

    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ConfigEntryState.LOADED

    # Enable the auxiliary sensor
    registry = await async_get_registry(hass)
    updated_entry = registry.async_update_entity(a_sensor, disabled_by=None)

    assert updated_entry != entry
    assert updated_entry.disabled is False

    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.auxiliary_slave_boiler_state")
    assert str(state.state) == STATE_OFF

    state = hass.states.get("binary_sensor.auxiliary_dhw_state")
    assert str(state.state) == STATE_OFF


async def test_anna_climate_binary_sensor_change(hass, mock_smile_anna):
    """Test change of climate related binary_sensor entities."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ConfigEntryState.LOADED

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

    n_sensor = "binary_sensor.adam_plugwise_notification"

    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ConfigEntryState.LOADED

    # Enable the notification sensor
    registry = await async_get_registry(hass)
    updated_entry = registry.async_update_entity(n_sensor, disabled_by=None)

    assert updated_entry != entry
    assert updated_entry.disabled is False

    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(n_sensor)
    assert str(state.state) == STATE_ON
    assert "unreachable" in state.attributes.get("WARNING_msg")[0]
    assert not state.attributes.get("error_msg")
    assert not state.attributes.get("other_msg")
