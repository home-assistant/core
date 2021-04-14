"""Tests for the Abode switch device."""
from unittest.mock import patch

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
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

AUTOMATION_ID = "switch.test_automation"
AUTOMATION_UID = "47fae27488f74f55b964a81a066c3a01"
DEVICE_ID = "switch.test_switch"
DEVICE_UID = "0012a4d3614cb7e2b8c9abea31d2fb2a"


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SWITCH_DOMAIN)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(AUTOMATION_ID)
    assert entry.unique_id == AUTOMATION_UID

    entry = entity_registry.async_get(DEVICE_ID)
    assert entry.unique_id == DEVICE_UID


async def test_attributes(hass):
    """Test the switch attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_OFF


async def test_switch_on(hass):
    """Test the switch can be turned on."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("abodepy.AbodeSwitch.switch_on") as mock_switch_on:
        assert await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()

        mock_switch_on.assert_called_once()


async def test_switch_off(hass):
    """Test the switch can be turned off."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("abodepy.AbodeSwitch.switch_off") as mock_switch_off:
        assert await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()

        mock_switch_off.assert_called_once()


async def test_automation_attributes(hass):
    """Test the automation attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(AUTOMATION_ID)
    # State is set based on "enabled" key in automation JSON.
    assert state.state == STATE_ON


async def test_turn_automation_off(hass):
    """Test the automation can be turned off."""
    with patch("abodepy.AbodeAutomation.enable") as mock_trigger:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_trigger.assert_called_once_with(False)


async def test_turn_automation_on(hass):
    """Test the automation can be turned on."""
    with patch("abodepy.AbodeAutomation.enable") as mock_trigger:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_trigger.assert_called_once_with(True)


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
