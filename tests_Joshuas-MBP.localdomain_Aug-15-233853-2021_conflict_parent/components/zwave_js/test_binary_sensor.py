"""Test the Z-Wave JS binary sensor platform."""
from zwave_js_server.event import Event

from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION
from homeassistant.const import DEVICE_CLASS_BATTERY, STATE_OFF, STATE_ON

from .common import (
    DISABLED_LEGACY_BINARY_SENSOR,
    ENABLED_LEGACY_BINARY_SENSOR,
    LOW_BATTERY_BINARY_SENSOR,
    NOTIFICATION_MOTION_BINARY_SENSOR,
    PROPERTY_DOOR_STATUS_BINARY_SENSOR,
)


async def test_low_battery_sensor(hass, multisensor_6, integration):
    """Test boolean binary sensor of type low battery."""
    state = hass.states.get(LOW_BATTERY_BINARY_SENSOR)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes["device_class"] == DEVICE_CLASS_BATTERY


async def test_enabled_legacy_sensor(hass, ecolink_door_sensor, integration):
    """Test enabled legacy boolean binary sensor."""
    node = ecolink_door_sensor
    # this node has Notification CC not (fully) implemented
    # so legacy binary sensor should be enabled

    state = hass.states.get(ENABLED_LEGACY_BINARY_SENSOR)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("device_class") is None

    # Test state updates from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 53,
            "args": {
                "commandClassName": "Binary Sensor",
                "commandClass": 48,
                "endpoint": 0,
                "property": "Any",
                "newValue": True,
                "prevValue": False,
                "propertyName": "Any",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(ENABLED_LEGACY_BINARY_SENSOR)
    assert state.state == STATE_ON


async def test_disabled_legacy_sensor(hass, multisensor_6, integration):
    """Test disabled legacy boolean binary sensor."""
    # this node has Notification CC implemented so legacy binary sensor should be disabled

    registry = await hass.helpers.entity_registry.async_get_registry()
    entity_id = DISABLED_LEGACY_BINARY_SENSOR
    state = hass.states.get(entity_id)
    assert state is None
    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test enabling legacy entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_notification_sensor(hass, multisensor_6, integration):
    """Test binary sensor created from Notification CC."""
    state = hass.states.get(NOTIFICATION_MOTION_BINARY_SENSOR)

    assert state
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == DEVICE_CLASS_MOTION


async def test_property_sensor_door_status(hass, lock_august_pro, integration):
    """Test property binary sensor with sensor mapping (doorStatus)."""
    node = lock_august_pro

    state = hass.states.get(PROPERTY_DOOR_STATUS_BINARY_SENSOR)
    assert state is not None
    assert state.state == STATE_OFF

    # open door
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "doorStatus",
                "newValue": "open",
                "prevValue": "closed",
                "propertyName": "doorStatus",
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(PROPERTY_DOOR_STATUS_BINARY_SENSOR)
    assert state.state == STATE_ON

    # close door
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "doorStatus",
                "newValue": "closed",
                "prevValue": "open",
                "propertyName": "doorStatus",
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(PROPERTY_DOOR_STATUS_BINARY_SENSOR)
    assert state.state == STATE_OFF
