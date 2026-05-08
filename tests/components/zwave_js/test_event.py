"""Test the Z-Wave JS event platform."""

from datetime import timedelta

from freezegun import freeze_time
import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.zwave_js.const import ATTR_URGENCY
from homeassistant.const import STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

BASIC_EVENT_VALUE_ENTITY = "event.honeywell_in_wall_smart_fan_control_event_value"
CENTRAL_SCENE_ENTITY = "event.node_51_scene_002"
BATTERY_LOW_EVENT_ENTITY = "event.keypad_v2_battery_low"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.EVENT]


async def test_basic(
    hass: HomeAssistant, client, fan_honeywell_39358, integration
) -> None:
    """Test the Basic CC event entity."""
    dt_util.now()
    fut = dt_util.now() + timedelta(minutes=1)
    node = fan_honeywell_39358
    state = hass.states.get(BASIC_EVENT_VALUE_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN

    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Basic",
                "commandClass": 32,
                "endpoint": 0,
                "property": "event",
                "propertyName": "event",
                "value": 255,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "min": 0,
                    "max": 255,
                    "label": "Event value",
                },
                "ccVersion": 1,
            },
        },
    )
    with freeze_time(fut):
        node.receive_event(event)

    state = hass.states.get(BASIC_EVENT_VALUE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    assert state.attributes == {
        "friendly_name": "honeywell_in_wall_smart_fan_control Event value",
        "event_type": "Basic event value",
        "event_types": ["Basic event value"],
        "value": 255,
    }


async def test_central_scene(
    hass: HomeAssistant, client, central_scene_node, integration
) -> None:
    """Test the Central Scene CC event entity."""
    dt_util.now()
    fut = dt_util.now() + timedelta(minutes=1)
    node = central_scene_node
    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN

    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "endpoint": 0,
                "commandClass": 91,
                "commandClassName": "Central Scene",
                "property": "scene",
                "propertyKey": "002",
                "propertyName": "scene",
                "propertyKeyName": "002",
                "ccVersion": 3,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Scene 002",
                    "min": 0,
                    "max": 255,
                    "states": {
                        "0": "KeyPressed",
                        "1": "KeyReleased",
                        "2": "KeyHeldDown",
                        "3": "KeyPressed2x",
                        "4": "KeyPressed3x",
                        "5": "KeyPressed4x",
                        "6": "KeyPressed5x",
                    },
                    "stateful": False,
                    "secret": False,
                },
                "value": 1,
            },
        },
    )
    with freeze_time(fut):
        node.receive_event(event)

    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    assert state.attributes == {
        "friendly_name": "Node 51 Scene 002",
        "event_type": "KeyReleased",
        "event_types": [
            "KeyHeldDown",
            "KeyPressed",
            "KeyPressed2x",
            "KeyPressed3x",
            "KeyPressed4x",
            "KeyPressed5x",
            "KeyReleased",
        ],
        "value": 1,
    }

    # Try invalid value
    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "endpoint": 0,
                "commandClass": 91,
                "commandClassName": "Central Scene",
                "property": "scene",
                "propertyKey": "002",
                "propertyName": "scene",
                "propertyKeyName": "002",
                "ccVersion": 3,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Scene 002",
                    "min": 0,
                    "max": 255,
                    "states": {
                        "0": "KeyPressed",
                        "1": "KeyReleased",
                        "2": "KeyHeldDown",
                        "3": "KeyPressed2x",
                        "4": "KeyPressed3x",
                        "5": "KeyPressed4x",
                        "6": "KeyPressed5x",
                    },
                    "stateful": False,
                    "secret": False,
                },
            },
        },
    )
    with freeze_time(fut + timedelta(minutes=10)):
        node.receive_event(event)

    # Nothing should have changed even though the time has changed
    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    assert state.attributes == {
        "friendly_name": "Node 51 Scene 002",
        "event_type": "KeyReleased",
        "event_types": [
            "KeyHeldDown",
            "KeyPressed",
            "KeyPressed2x",
            "KeyPressed3x",
            "KeyPressed4x",
            "KeyPressed5x",
            "KeyReleased",
        ],
        "value": 1,
    }


def _battery_notification_event(node_id: int, urgency: int) -> Event:
    """Build a Battery CC notification event."""
    return Event(
        type="notification",
        data={
            "source": "node",
            "event": "notification",
            "nodeId": node_id,
            "endpointIndex": 0,
            "ccId": 128,  # Battery CC
            "args": {
                "eventType": "battery low",
                "urgency": urgency,
            },
        },
    )


async def test_battery_low_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    ring_keypad: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the Battery CC battery low event entity."""
    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes["event_types"] == ["soon", "now"]

    entity_entry = entity_registry.async_get(BATTERY_LOW_EVENT_ENTITY)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert entity_entry.translation_key == "battery_low"
    assert entity_entry.unique_id.endswith(".battery_low")

    fut = dt_util.now() + timedelta(minutes=1)
    with freeze_time(fut):
        ring_keypad.receive_event(
            _battery_notification_event(ring_keypad.node_id, urgency=1)
        )
        await hass.async_block_till_done()

    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "soon"
    assert state.attributes[ATTR_URGENCY] == 1

    fut2 = fut + timedelta(hours=2)
    with freeze_time(fut2):
        ring_keypad.receive_event(
            _battery_notification_event(ring_keypad.node_id, urgency=2)
        )
        await hass.async_block_till_done()

    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == dt_util.as_utc(fut2).isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "now"
    assert state.attributes[ATTR_URGENCY] == 2


async def test_battery_low_event_no_urgency_ignored(
    hass: HomeAssistant,
    client,
    ring_keypad: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that urgency=NO does not trigger the battery low event entity."""
    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN

    ring_keypad.receive_event(
        _battery_notification_event(ring_keypad.node_id, urgency=0)
    )
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_battery_low_event_other_notifications_ignored(
    hass: HomeAssistant,
    client,
    ring_keypad: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that non-Battery CC notifications do not trigger the entity."""
    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN

    # Notification CC (113) should be ignored by the battery low entity
    other_event = Event(
        type="notification",
        data={
            "source": "node",
            "event": "notification",
            "nodeId": ring_keypad.node_id,
            "endpointIndex": 0,
            "ccId": 113,
            "args": {
                "type": 7,
                "label": "Home Security",
                "event": 3,
                "eventLabel": "Tampering, product cover removed",
            },
        },
    )
    ring_keypad.receive_event(other_event)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_LOW_EVENT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
