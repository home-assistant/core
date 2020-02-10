"""Test for the Abode switch device."""
import abodepy.helpers.constants as CONST

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

from .common import setup_platform

from tests.common import load_fixture

AUTOMATION_ID = "47fae27488f74f55b964a81a066c3a01"
DEVICE_ID = "0012a4d3614cb7e2b8c9abea31d2fb2a"


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SWITCH_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("switch.test_automation")
    assert entry.unique_id == AUTOMATION_ID

    entry = entity_registry.async_get("switch.test_switch")
    assert entry.unique_id == DEVICE_ID


async def test_switch_attributes(hass, requests_mock):
    """Test the switch attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get("switch.test_switch")
    assert state.state == "off"


async def test_automation_attributes(hass, requests_mock):
    """Test the automation attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get("switch.test_automation")
    # State is set based on "enabled" key in automation JSON.
    assert state.state == "on"


async def test_turn_automation_off(hass, requests_mock):
    """Test the automation can be turned off."""
    await setup_platform(hass, SWITCH_DOMAIN)
    requests_mock.patch(
        str.replace(CONST.AUTOMATION_ID_URL, "$AUTOMATIONID$", AUTOMATION_ID),
        text=load_fixture("abode_automation_changed.json"),
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test_automation"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_automation")
    assert state.state == "off"


async def test_turn_automation_on(hass, requests_mock):
    """Test the automation can be turned on."""
    await setup_platform(hass, SWITCH_DOMAIN)
    requests_mock.patch(
        str.replace(CONST.AUTOMATION_ID_URL, "$AUTOMATIONID$", AUTOMATION_ID),
        text=load_fixture("abode_automation.json"),
    )

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test_automation"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_automation")
    assert state.state == "on"


async def test_trigger_automation(hass, requests_mock):
    """Test the trigger automation service."""
    await setup_platform(hass, SWITCH_DOMAIN)
    requests_mock.patch(
        str.replace(CONST.AUTOMATION_APPLY_URL, "$AUTOMATIONID$", AUTOMATION_ID),
        text="",
    )

    await hass.services.async_call(
        "abode",
        "trigger_automation",
        {"entity_id": "switch.test_automation"},
        blocking=True,
    )
    await hass.async_block_till_done()
