"""The tests for Philips Hue device triggers for V2 bridge."""
from aiohue.v2.models.button import ButtonEvent

from homeassistant.components import hue
from homeassistant.components.hue.v2.device import async_setup_devices
from homeassistant.components.hue.v2.hue_event import async_setup_hue_events

from .conftest import setup_platform

from tests.common import (
    assert_lists_same,
    async_capture_events,
    async_get_device_automations,
)


async def test_hue_event(hass, mock_bridge_v2, v2_resources_test_data):
    """Test hue button events."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, ["binary_sensor", "sensor"])
    await async_setup_devices(mock_bridge_v2)
    await async_setup_hue_events(mock_bridge_v2)

    events = async_capture_events(hass, "hue_event")

    # Emit button update event
    btn_event = {
        "button": {"last_event": "short_release"},
        "id": "c658d3d8-a013-4b81-8ac6-78b248537e70",
        "metadata": {"control_id": 1},
        "type": "button",
    }
    mock_bridge_v2.api.emit_event("update", btn_event)

    # wait for the event
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["id"] == "wall_switch_with_2_controls_button"
    assert events[0].data["unique_id"] == btn_event["id"]
    assert events[0].data["type"] == btn_event["button"]["last_event"]
    assert events[0].data["subtype"] == btn_event["metadata"]["control_id"]


async def test_get_triggers(hass, mock_bridge_v2, v2_resources_test_data, device_reg):
    """Test we get the expected triggers from a hue remote."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, ["binary_sensor", "sensor"])

    # Get triggers for `Wall switch with 2 controls`
    hue_wall_switch_device = device_reg.async_get_device(
        {(hue.DOMAIN, "3ff06175-29e8-44a8-8fe7-af591b0025da")}
    )
    triggers = await async_get_device_automations(
        hass, "trigger", hue_wall_switch_device.id
    )

    trigger_batt = {
        "platform": "device",
        "domain": "sensor",
        "device_id": hue_wall_switch_device.id,
        "type": "battery_level",
        "entity_id": "sensor.wall_switch_with_2_controls_battery",
    }

    expected_triggers = [
        trigger_batt,
        *(
            {
                "platform": "device",
                "domain": hue.DOMAIN,
                "device_id": hue_wall_switch_device.id,
                "unique_id": hue_wall_switch_device.id,
                "type": event_type,
                "subtype": control_id,
            }
            for event_type in (x.value for x in ButtonEvent if x != ButtonEvent.UNKNOWN)
            for control_id in range(1, 3)
        ),
    ]

    assert_lists_same(triggers, expected_triggers)
