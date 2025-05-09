"""Test the Z-Wave JS binary sensor platform."""

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    DISABLED_LEGACY_BINARY_SENSOR,
    ENABLED_LEGACY_BINARY_SENSOR,
    LOW_BATTERY_BINARY_SENSOR,
    NOTIFICATION_MOTION_BINARY_SENSOR,
    PROPERTY_DOOR_STATUS_BINARY_SENSOR,
    TAMPER_SENSOR,
)

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_low_battery_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, multisensor_6, integration
) -> None:
    """Test boolean binary sensor of type low battery."""
    state = hass.states.get(LOW_BATTERY_BINARY_SENSOR)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY

    entity_entry = entity_registry.async_get(LOW_BATTERY_BINARY_SENSOR)

    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_enabled_legacy_sensor(
    hass: HomeAssistant, ecolink_door_sensor, integration
) -> None:
    """Test enabled legacy boolean binary sensor."""
    node = ecolink_door_sensor
    # this node has Notification CC not (fully) implemented
    # so legacy binary sensor should be enabled

    state = hass.states.get(ENABLED_LEGACY_BINARY_SENSOR)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None

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
                "newValue": None,
                "prevValue": True,
                "propertyName": "Any",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(ENABLED_LEGACY_BINARY_SENSOR)
    assert state.state == STATE_UNKNOWN


async def test_disabled_legacy_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, multisensor_6, integration
) -> None:
    """Test disabled legacy boolean binary sensor."""
    # this node has Notification CC implemented so legacy binary sensor should be disabled

    entity_id = DISABLED_LEGACY_BINARY_SENSOR
    state = hass.states.get(entity_id)
    assert state is None
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling legacy entity
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_notification_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, multisensor_6, integration
) -> None:
    """Test binary sensor created from Notification CC."""
    state = hass.states.get(NOTIFICATION_MOTION_BINARY_SENSOR)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOTION

    state = hass.states.get(TAMPER_SENSOR)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.TAMPER

    entity_entry = entity_registry.async_get(TAMPER_SENSOR)

    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_notification_off_state(
    hass: HomeAssistant,
    lock_popp_electric_strike_lock_control: Node,
) -> None:
    """Test the description off_state attribute of certain notification sensors."""
    node = lock_popp_electric_strike_lock_control
    # Remove all other values except the door state value.
    node.values = {
        value_id: value
        for value_id, value in node.values.items()
        if value_id == "62-113-0-Access Control-Door state"
    }

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    door_states = [
        state
        for state in hass.states.async_all("binary_sensor")
        if state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    ]

    # Only one entity should be created for the Door state notification states.
    assert len(door_states) == 1

    state = door_states[0]
    assert state
    assert state.entity_id == "binary_sensor.node_62_window_door_is_open"


async def test_property_sensor_door_status(
    hass: HomeAssistant, lock_august_pro, integration
) -> None:
    """Test property binary sensor with sensor mapping (doorStatus)."""
    node = lock_august_pro

    state = hass.states.get(PROPERTY_DOOR_STATUS_BINARY_SENSOR)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR

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
    assert state
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
    assert state
    assert state.state == STATE_OFF

    # door state unknown
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
                "newValue": None,
                "prevValue": "open",
                "propertyName": "doorStatus",
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(PROPERTY_DOOR_STATUS_BINARY_SENSOR)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_config_parameter_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    climate_adc_t3000,
    integration,
) -> None:
    """Test config parameter binary sensor is created."""
    binary_sensor_entity_id = "binary_sensor.adc_t3000_system_configuration_override"
    entity_entry = entity_registry.async_get(binary_sensor_entity_id)
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC

    updated_entry = entity_registry.async_update_entity(
        binary_sensor_entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(binary_sensor_entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_smoke_co_notification_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zcombo_smoke_co_alarm: Node,
    integration: MockConfigEntry,
) -> None:
    """Test smoke and CO notification sensors with diagnostic states."""
    # Test smoke alarm sensor
    smoke_sensor = "binary_sensor.zcombo_g_smoke_co_alarm_smoke_detected"
    state = hass.states.get(smoke_sensor)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.SMOKE
    entity_entry = entity_registry.async_get(smoke_sensor)
    assert entity_entry
    assert entity_entry.entity_category != EntityCategory.DIAGNOSTIC

    # Test smoke alarm diagnostic sensor
    smoke_diagnostic = "binary_sensor.zcombo_g_smoke_co_alarm_smoke_alarm_test"
    state = hass.states.get(smoke_diagnostic)
    assert state
    assert state.state == STATE_OFF
    entity_entry = entity_registry.async_get(smoke_diagnostic)
    assert entity_entry
    assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC

    # Test CO alarm sensor
    co_sensor = "binary_sensor.zcombo_g_smoke_co_alarm_carbon_monoxide_detected"
    state = hass.states.get(co_sensor)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CO
    entity_entry = entity_registry.async_get(co_sensor)
    assert entity_entry
    assert entity_entry.entity_category != EntityCategory.DIAGNOSTIC

    # Test diagnostic entities
    entity_ids = [
        "binary_sensor.zcombo_g_smoke_co_alarm_smoke_alarm_test",
        "binary_sensor.zcombo_g_smoke_co_alarm_alarm_silenced",
        "binary_sensor.zcombo_g_smoke_co_alarm_replacement_required_end_of_life",
        "binary_sensor.zcombo_g_smoke_co_alarm_alarm_silenced_2",
        "binary_sensor.zcombo_g_smoke_co_alarm_system_hardware_failure",
        "binary_sensor.zcombo_g_smoke_co_alarm_low_battery_level",
    ]
    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC

    # Test state updates for smoke alarm
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 3,
            "args": {
                "commandClassName": "Notification",
                "commandClass": 113,
                "endpoint": 0,
                "property": "Smoke Alarm",
                "propertyKey": "Sensor status",
                "newValue": 2,
                "prevValue": 0,
                "propertyName": "Smoke Alarm",
                "propertyKeyName": "Sensor status",
            },
        },
    )
    zcombo_smoke_co_alarm.receive_event(event)
    await hass.async_block_till_done()  # Wait for state change to be processed
    # Get a fresh state after the sleep
    state = hass.states.get(smoke_sensor)
    assert state is not None, "Smoke sensor state should not be None"
    assert state.state == STATE_ON, (
        f"Expected smoke sensor state to be 'on', got '{state.state}'"
    )

    # Test state updates for CO alarm
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 3,
            "args": {
                "commandClassName": "Notification",
                "commandClass": 113,
                "endpoint": 0,
                "property": "CO Alarm",
                "propertyKey": "Sensor status",
                "newValue": 2,
                "prevValue": 0,
                "propertyName": "CO Alarm",
                "propertyKeyName": "Sensor status",
            },
        },
    )
    zcombo_smoke_co_alarm.receive_event(event)
    await hass.async_block_till_done()  # Wait for state change to be processed
    # Get a fresh state after the sleep
    state = hass.states.get(co_sensor)
    assert state is not None, "CO sensor state should not be None"
    assert state.state == STATE_ON, (
        f"Expected CO sensor state to be 'on', got '{state.state}'"
    )

    # Test diagnostic state updates for smoke alarm
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 3,
            "args": {
                "commandClassName": "Notification",
                "commandClass": 113,
                "endpoint": 0,
                "property": "Smoke Alarm",
                "propertyKey": "Alarm status",
                "newValue": 3,
                "prevValue": 0,
                "propertyName": "Smoke Alarm",
                "propertyKeyName": "Alarm status",
            },
        },
    )
    zcombo_smoke_co_alarm.receive_event(event)
    await hass.async_block_till_done()  # Wait for state change to be processed
    # Get a fresh state after the sleep
    state = hass.states.get(smoke_diagnostic)
    assert state is not None, "Smoke diagnostic state should not be None"
    assert state.state == STATE_ON, (
        f"Expected smoke diagnostic state to be 'on', got '{state.state}'"
    )
