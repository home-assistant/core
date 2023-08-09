"""Philips Hue Event platform tests for V2 bridge/api."""
from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
)
from homeassistant.core import HomeAssistant

from .conftest import setup_platform
from .const import FAKE_DEVICE, FAKE_ROTARY, FAKE_ZIGBEE_CONNECTIVITY


async def test_event(
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test event entity for Hue integration."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, "event")
    # 7 entities should be created from test data
    assert len(hass.states.async_all()) == 7

    # pick one of the remote buttons
    state = hass.states.get("event.hue_dimmer_switch_with_4_controls_button_1")
    assert state
    assert state.state == "unknown"
    assert state.name == "Hue Dimmer switch with 4 controls Button 1"
    # check event_types
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "repeat",
        "short_release",
        "long_press",
        "long_release",
    ]
    # trigger firing 'initial_press' event from the device
    btn_event = {
        "button": {"last_event": "initial_press"},
        "id": "f92aa267-1387-4f02-9950-210fb7ca1f5a",
        "metadata": {"control_id": 1},
        "type": "button",
    }
    mock_bridge_v2.api.emit_event("update", btn_event)
    await hass.async_block_till_done()
    state = hass.states.get("event.hue_dimmer_switch_with_4_controls_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"
    # trigger firing 'long_release' event from the device
    btn_event = {
        "button": {"last_event": "long_release"},
        "id": "f92aa267-1387-4f02-9950-210fb7ca1f5a",
        "metadata": {"control_id": 1},
        "type": "button",
    }
    mock_bridge_v2.api.emit_event("update", btn_event)
    await hass.async_block_till_done()
    state = hass.states.get("event.hue_dimmer_switch_with_4_controls_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "long_release"


async def test_sensor_add_update(hass: HomeAssistant, mock_bridge_v2) -> None:
    """Test Event entity for newly added Relative Rotary resource."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])
    await setup_platform(hass, mock_bridge_v2, "event")

    test_entity_id = "event.hue_mocked_device_relative_rotary"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake relative_rotary entity by emitting event
    mock_bridge_v2.api.emit_event("add", FAKE_ROTARY)
    await hass.async_block_till_done()

    # the entity should now be available
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "Hue mocked device Relative Rotary"
    # check event_types
    assert state.attributes[ATTR_EVENT_TYPES] == ["clock_wise", "counter_clock_wise"]

    # test update of entity works on incoming event
    btn_event = {
        "id": "fake_relative_rotary",
        "relative_rotary": {
            "last_event": {
                "action": "repeat",
                "rotation": {
                    "direction": "counter_clock_wise",
                    "steps": 60,
                    "duration": 400,
                },
            }
        },
        "type": "relative_rotary",
    }
    mock_bridge_v2.api.emit_event("update", btn_event)
    await hass.async_block_till_done()
    state = hass.states.get(test_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "counter_clock_wise"
    assert state.attributes["action"] == "repeat"
    assert state.attributes["steps"] == 60
    assert state.attributes["duration"] == 400
