"""Tests for the Abode switch device."""
from unittest.mock import patch

import abodepy.helpers.constants as CONST

from homeassistant.components.abode import (
    DOMAIN as ABODE_DOMAIN,
    SERVICE_TRIGGER_AUTOMATION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from .common import setup_platform

from tests.common import load_fixture

AUTOMATION_ID = "switch.test_automation"
AUTOMATION_UID = "47fae27488f74f55b964a81a066c3a01"
DEVICE_ID = "switch.test_switch"
DEVICE_UID = "0012a4d3614cb7e2b8c9abea31d2fb2a"


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SWITCH_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get(AUTOMATION_ID)
    assert entry.unique_id == AUTOMATION_UID

    entry = entity_registry.async_get(DEVICE_ID)
    assert entry.unique_id == DEVICE_UID


async def test_switch_attributes(hass, requests_mock):
    """Test the switch attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_OFF


async def test_automation_attributes(hass, requests_mock):
    """Test the automation attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(AUTOMATION_ID)
    # State is set based on "enabled" key in automation JSON.
    assert state.state == STATE_ON


async def test_turn_automation_off(hass, requests_mock):
    """Test the automation can be turned off."""
    await setup_platform(hass, SWITCH_DOMAIN)
    requests_mock.patch(
        str.replace(CONST.AUTOMATION_ID_URL, "$AUTOMATIONID$", AUTOMATION_UID),
        text=load_fixture("abode_automation_changed.json"),
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: AUTOMATION_ID}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(AUTOMATION_ID)
    assert state.state == STATE_OFF


async def test_turn_automation_on(hass, requests_mock):
    """Test the automation can be turned on."""
    await setup_platform(hass, SWITCH_DOMAIN)
    requests_mock.patch(
        str.replace(CONST.AUTOMATION_ID_URL, "$AUTOMATIONID$", AUTOMATION_UID),
        text=load_fixture("abode_automation.json"),
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: AUTOMATION_ID}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(AUTOMATION_ID)
    assert state.state == STATE_ON


async def test_trigger_automation(hass, requests_mock):
    """Test the trigger automation service."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("abodepy.AbodeAutomation.trigger") as mock:
        await hass.services.async_call(
            ABODE_DOMAIN,
            SERVICE_TRIGGER_AUTOMATION,
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_called_once()
