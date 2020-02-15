"""Tests for the Abode alarm control panel device."""
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN

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
    assert state.state == "disarmed"
    assert state.attributes.get("device_id") == "area_1"
    assert not state.attributes.get("battery_backup")
    assert not state.attributes.get("cellular_backup")
    assert state.attributes.get("friendly_name") == "Abode Alarm"
    assert state.attributes.get("supported_features") == 3


async def test_set_alarm_away(hass, requests_mock):
    """Test the alarm control panel can be set to away."""
    await setup_platform(hass, ALARM_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/panel/mode/1/away",
        text='{ "area": "1", "mode": "away"}',
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": "alarm_control_panel.abode_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_set_alarm_home(hass, requests_mock):
    """Test the alarm control panel can be set to home."""
    await setup_platform(hass, ALARM_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/panel/mode/1/home",
        text='{ "area": "1", "mode": "home"}',
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_home",
        {"entity_id": "alarm_control_panel.abode_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_set_alarm_standby(hass, requests_mock):
    """Test the alarm control panel can be set to standby."""
    await setup_platform(hass, ALARM_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/panel/mode/1/standby",
        text='{ "area": "1", "mode": "standby"}',
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_disarm",
        {"entity_id": "alarm_control_panel.abode_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()
