"""Test the Envisalink binary sensors."""

from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_sensor_state(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test the createion and values of the Envisalink binary sensors."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    state = hass.states.get("sensor.test_alarm_name_partition_1_keypad")
    assert state
    assert state.state == "N/A"


async def test_sensor_update(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test updating the keypad's alpha state."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    controller.controller.alarm_state["partition"][1]["status"]["alpha"] = "alpha_state"
    controller.async_partition_updated_callback([1])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_alarm_name_partition_1_keypad")
    assert state
    assert state.state == "alpha_state"
