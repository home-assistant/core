"""Tests for button platform."""
from homeassistant.components import flux_led
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    FLUX_DISCOVERY,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mock_config_entry_for_bulb,
    _mocked_bulb,
    _mocked_switch,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry


async def test_button_reboot(hass: HomeAssistant) -> None:
    """Test a smart plug can be rebooted."""
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

    entity_id = "button.bulb_rgbcw_ddeeff_restart"

    assert hass.states.get(entity_id)

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.async_reboot.assert_called_once()


async def test_button_unpair_remotes(hass: HomeAssistant) -> None:
    """Test that remotes can be unpaired."""
    _mock_config_entry_for_bulb(hass)
    bulb = _mocked_bulb()
    bulb.discovery = FLUX_DISCOVERY
    with _patch_discovery(device=FLUX_DISCOVERY), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "button.bulb_rgbcw_ddeeff_unpair_remotes"
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_unpair_remotes.assert_called_once()
