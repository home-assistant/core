"""Tests for the Abode alarm control panel device."""
from unittest.mock import patch

from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_DISARMED,
)

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, ALARM_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("alarm_control_panel.abode_alarm")
    # Abode alarm device unique_id is the MAC address
    assert entry.unique_id == "001122334455"


async def test_automation_attributes(hass, requests_mock):
    """Test the alarm control panel attributes are correct."""
    await setup_platform(hass, ALARM_DOMAIN)

    state = hass.states.get("alarm_control_panel.abode_alarm")
    assert state.state == STATE_ALARM_DISARMED
    assert state.attributes.get(ATTR_DEVICE_ID) == "area_1"
    assert not state.attributes.get("battery_backup")
    assert not state.attributes.get("cellular_backup")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Abode Alarm"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3


async def test_set_alarm_away(hass, requests_mock):
    """Test the alarm control panel can be set to away."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("abodepy.ALARM.AbodeAlarm.set_away") as mock_set_away:
        await hass.services.async_call(
            "alarm_control_panel",
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: "alarm_control_panel.abode_alarm"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_away.assert_called_once()


async def test_set_alarm_home(hass, requests_mock):
    """Test the alarm control panel can be set to home."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("abodepy.ALARM.AbodeAlarm.set_home") as mock_set_home:
        await hass.services.async_call(
            "alarm_control_panel",
            SERVICE_ALARM_ARM_HOME,
            {ATTR_ENTITY_ID: "alarm_control_panel.abode_alarm"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_home.assert_called_once()


async def test_set_alarm_standby(hass, requests_mock):
    """Test the alarm control panel can be set to standby."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("abodepy.ALARM.AbodeAlarm.set_standby") as mock_set_standby:
        await hass.services.async_call(
            "alarm_control_panel",
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: "alarm_control_panel.abode_alarm"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_standby.assert_called_once()
