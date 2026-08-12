"""Tests for all Papouch entity platforms."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.papouch.const import DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_all_entities(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test reading and writing data across all supported entities."""
    _, _, mock_device = mock_papouch_client

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    mac = "00:11:22:33:44:55"

    # --- SENSOR ---
    sensor_id = registry.async_get_entity_id("sensor", DOMAIN, f"{mac}_temperature_1")
    state = hass.states.get(sensor_id)
    assert state
    assert state.state == "22.5"
    assert state.attributes["unit_of_measurement"] == "°C"

    mock_device.get_supported_sensors.return_value = [
        {"item_id": "1", "type": "temperature", "name": "Temp 1", "unit": "°F"}
    ]
    await mock_config_entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(sensor_id)
    assert state.attributes["unit_of_measurement"] == "°F"

    # --- BINARY SENSOR ---
    binary_id = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{mac}_input_1")
    state = hass.states.get(binary_id)
    assert state
    assert state.state == "on"

    # --- SWITCH ---
    switch_id = registry.async_get_entity_id("switch", DOMAIN, f"{mac}_switch_1")
    state = hass.states.get(switch_id)
    assert state
    assert state.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": switch_id}, blocking=True
    )
    mock_device.turn_off_switch.assert_called_once_with("1")

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": switch_id}, blocking=True
    )
    mock_device.turn_on_switch.assert_called_once_with("1")

    # --- BUTTON ---
    btn_id = registry.async_get_entity_id("button", DOMAIN, f"{mac}_btn_reset")
    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {"entity_id": btn_id}, blocking=True
    )
    mock_device.execute_button_command.assert_called_once_with("reset")

    # --- NUMBER ---
    num_id = registry.async_get_entity_id("number", DOMAIN, f"{mac}_limit_1")
    await hass.services.async_call(
        NUMBER_DOMAIN, "set_value", {"entity_id": num_id, "value": 50}, blocking=True
    )
    mock_device.set_number_value.assert_called_once_with("limit", "1", 50.0)

    # --- SELECT ---
    select_id = registry.async_get_entity_id("select", DOMAIN, f"{mac}_mode_1")
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {"entity_id": select_id, "option": "B"},
        blocking=True,
    )
    mock_device.set_select_option.assert_called_once_with("mode", "1", "B")
