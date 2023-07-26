"""Philips Hue Event platform tests for V2 bridge/api."""
from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
)
from homeassistant.core import HomeAssistant

from .conftest import setup_platform


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
    # the switch endpoint has no label so the entity name should be the device itself
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
