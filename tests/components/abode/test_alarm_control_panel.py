"""Tests for the Abode alarm control panel device."""
from unittest.mock import patch

import abodepy.helpers.constants as CONST

from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)

from .common import setup_platform

DEVICE_ID = "alarm_control_panel.abode_alarm"


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, ALARM_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get(DEVICE_ID)
    # Abode alarm device unique_id is the MAC address
    assert entry.unique_id == "001122334455"


async def test_automation_attributes(hass):
    """Test the alarm control panel attributes are correct."""
    await setup_platform(hass, ALARM_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_ALARM_DISARMED
    assert state.attributes.get(ATTR_DEVICE_ID) == "area_1"
    assert not state.attributes.get("battery_backup")
    assert not state.attributes.get("cellular_backup")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Abode Alarm"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3


async def test_set_alarm_away(hass, requests_mock):
    """Test the alarm control panel can be set to away."""
    requests_mock.put(
        CONST.get_panel_mode_url("1", CONST.MODE_AWAY),
        json={"area": "1", "mode": CONST.MODE_AWAY},
    )

    with patch("abodepy.AbodeEventController.add_device_callback") as mock_callback:
        await setup_platform(hass, ALARM_DOMAIN)

        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        update_callback = mock_callback.call_args[0][1]
        await hass.async_add_executor_job(update_callback, "area_1")
        await hass.async_block_till_done()

        state = hass.states.get(DEVICE_ID)
        assert state.state == STATE_ALARM_ARMED_AWAY


async def test_set_alarm_home(hass, requests_mock):
    """Test the alarm control panel can be set to home."""
    requests_mock.put(
        CONST.get_panel_mode_url("1", CONST.MODE_HOME),
        json={"area": "1", "mode": CONST.MODE_HOME},
    )

    with patch("abodepy.AbodeEventController.add_device_callback") as mock_callback:
        await setup_platform(hass, ALARM_DOMAIN)
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        update_callback = mock_callback.call_args[0][1]
        await hass.async_add_executor_job(update_callback, "area_1")
        await hass.async_block_till_done()

        state = hass.states.get(DEVICE_ID)
        assert state.state == STATE_ALARM_ARMED_HOME


async def test_set_alarm_standby(hass, requests_mock):
    """Test the alarm control panel can be set to standby."""
    requests_mock.put(
        CONST.get_panel_mode_url("1", CONST.MODE_STANDBY),
        json={"area": "1", "mode": CONST.MODE_STANDBY},
    )

    with patch("abodepy.AbodeEventController.add_device_callback") as mock_callback:
        await setup_platform(hass, ALARM_DOMAIN)
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        update_callback = mock_callback.call_args[0][1]
        await hass.async_add_executor_job(update_callback, "area_1")
        await hass.async_block_till_done()

        state = hass.states.get(DEVICE_ID)
        assert state.state == STATE_ALARM_DISARMED
