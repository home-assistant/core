"""Tests for switch platform."""
from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_switch,
    _patch_discovery,
    _patch_wifibulb,
    async_mock_device_turn_off,
    async_mock_device_turn_on,
)

from tests.common import MockConfigEntry


async def test_switch_on_off(hass: HomeAssistant) -> None:
    """Test a switch light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    switch = _mocked_switch()
    with _patch_discovery(device=switch), _patch_wifibulb(device=switch):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.rgbw_controller_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, switch)
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.async_turn_on.assert_called_once()
    switch.async_turn_on.reset_mock()

    await async_mock_device_turn_on(hass, switch)
    assert hass.states.get(entity_id).state == STATE_ON
