"""Tests for select platform."""
from flux_led.protocol import PowerRestoreState

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_switch,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry


async def test_switch_power_restore_state(hass: HomeAssistant) -> None:
    """Test a smart plug power restore state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    switch = _mocked_switch()
    with _patch_discovery(), _patch_wifibulb(device=switch):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.bulb_rgbcw_ddeeff_power_restored"

    state = hass.states.get(entity_id)
    assert state.state == "Last State"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Always On"},
        blocking=True,
    )
    switch.async_set_power_restore.assert_called_once_with(
        channel1=PowerRestoreState.ALWAYS_ON
    )
