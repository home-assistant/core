"""Tests for the switch domain for Flo by Moen."""
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.components.switch import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID


async def test_valve_switches(hass, config_entry, aioclient_mock_fixture):
    """Test Flo by Moen valve switches."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()

    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 1

    entity_id = "switch.shutoff_valve"
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
