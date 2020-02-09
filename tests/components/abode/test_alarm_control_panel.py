"""Test for the Abode alarm control panel device."""
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
