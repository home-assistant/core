"""Test the Envisalink binary sensors."""

from unittest.mock import patch

from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.components.envisalink.controller import EnvisalinkController
from homeassistant.components.envisalink.pyenvisalink.alarm_panel import (
    EnvisalinkAlarmPanel,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TOGGLE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def _async_toggle_switch(
    hass: HomeAssistant, controller: EnvisalinkController, state: bool
):
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.test_alarm_name_zone_1_bypass"},
        blocking=True,
    )
    controller.controller.alarm_state["zone"][1]["bypassed"] = state
    controller.async_zone_bypass_update([1])
    await hass.async_block_till_done()


async def test_switch_state(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test the createion and values of the Envisalink binary sensors."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    state = hass.states.get("switch.test_alarm_name_zone_1_bypass")
    assert state
    assert state.state == STATE_OFF


async def test_switch_toggle(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test toggling the bypass switch."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    with patch.object(
        EnvisalinkAlarmPanel,
        "toggle_zone_bypass",
        autospec=True,
    ):
        er.async_get(hass)

        # Toggle switch on
        await _async_toggle_switch(hass, controller, True)

        state = hass.states.get("switch.test_alarm_name_zone_1_bypass")
        assert state
        assert state.state == STATE_ON

        # Toggle switch off
        await _async_toggle_switch(hass, controller, False)

        state = hass.states.get("switch.test_alarm_name_zone_1_bypass")
        assert state
        assert state.state == STATE_OFF
