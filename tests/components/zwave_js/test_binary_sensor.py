"""Test the Z-Wave JS binary sensor platform."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node, NodeDataType

from homeassistant.components import automation
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    DISABLED_LEGACY_BINARY_SENSOR,
    ENABLED_LEGACY_BINARY_SENSOR,
    NOTIFICATION_MOTION_BINARY_SENSOR,
    PROPERTY_DOOR_STATUS_BINARY_SENSOR,
    TAMPER_SENSOR,
)

from tests.common import MockConfigEntry, async_fire_time_changed


def _add_door_tilt_state_value(node_state: dict[str, Any]) -> dict[str, Any]:
    """Return a node state with a Door tilt state notification value added."""
    updated_state = copy.deepcopy(node_state)
    updated_state["values"].append(
        {
            "commandClass": 113,
            "commandClassName": "Notification",
            "property": "Access Control",
            "propertyKey": "Door tilt state",
            "propertyName": "Access Control",
            "propertyKeyName": "Door tilt state",
            "ccVersion": 8,
            "metadata": {
                "type": "number",
                "readable": True,
                "writeable": False,
                "label": "Door tilt state",
                "ccSpecific": {"notificationType": 6},
                "min": 0,
                "max": 255,
                "states": {
                    "0": "Window/door is not tilted",
                    "1": "Window/door is tilted",
                },
                "stateful": True,
                "secret": False,
            },
            "value": 0,
        }
    )
    return updated_state


def _add_barrier_status_value(node_state: dict[str, Any]) -> dict[str, Any]:
    """Return a node state with a Barrier status Access Control notification value added."""
    updated_state = copy.deepcopy(node_state)
    updated_state["values"].append(
        {
            "commandClass": 113,
            "commandClassName": "Notification",
            "property": "Access Control",
            "propertyKey": "Barrier status",
            "propertyName": "Access Control",
            "propertyKeyName": "Barrier status",
            "ccVersion": 8,
            "metadata": {
                "type": "number",
                "readable": True,
                "writeable": False,
                "label": "Barrier status",
                "ccSpecific": {"notificationType": 6},
                "min": 0,
                "max": 255,
                "states": {
                    "0": "idle",
                    "64": "Barrier performing initialization process",
                    "72": "Barrier safety beam obstacle",
                },
                "stateful": True,
                "secret": False,
            },
            "value": 0,
        }
    )
    return updated_state


def _move_notification_values_to_endpoint(
    node_state: dict[str, Any], endpoint: int
) -> dict[str, Any]:
    """Return a node state with all Notification CC values moved to a different endpoint."""
    updated_state = copy.deepcopy(node_state)
    for value_data in updated_state["values"]:
        if value_data.get("commandClass") == 113:
            value_data["endpoint"] = endpoint
    # Add the target endpoint to the endpoints list with the Notification CC.
    ep0 = updated_state["endpoints"][0]
    updated_state["endpoints"].append(
        {
            "nodeId": ep0["nodeId"],
            "index": endpoint,
            "deviceClass": ep0["deviceClass"],
            "commandClasses": [cc for cc in ep0["commandClasses"] if cc["id"] == 113],
        }
    )
    return updated_state


def _add_lock_state_notification_states(node_state: dict[str, Any]) -> dict[str, Any]:
    """Return a node state with Access Control lock state notification states 1-4."""
    updated_state = copy.deepcopy(node_state)
    for value_data in updated_state["values"]:
        if (
            value_data.get("commandClass") == 113
            and value_data.get("property") == "Access Control"
            and value_data.get("propertyKey") == "Lock state"
        ):
            value_data["metadata"].setdefault("states", {}).update(
                {
                    "1": "Manual lock operation",
                    "2": "Manual unlock operation",
                    "3": "RF lock operation",
                    "4": "RF unlock operation",
                }
            )
            break
    return updated_state


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_battery_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ring_keypad: Node,
    integration: MockConfigEntry,
) -> None:
    """Test boolean battery binary sensors."""
    entity_id = "binary_sensor.keypad_v2_low_battery_level"
    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY

    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC

    disabled_binary_sensor_battery_entities = (
        "binary_sensor.keypad_v2_battery_is_disconnected",
        "binary_sensor.keypad_v2_fluid_is_low",
        "binary_sensor.keypad_v2_overheating",
        "binary_sensor.keypad_v2_rechargeable",
        "binary_sensor.keypad_v2_used_as_backup",
    )

    for entity_id in disabled_binary_sensor_battery_entities:
        state = hass.states.get(entity_id)
        assert state is None  # disabled by default

        entity_entry = entity_registry.async_get(entity_id)

        assert entity_entry
        assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        entity_registry.async_update_entity(entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    for entity_id in disabled_binary_sensor_battery_entities:
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF


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


async def test_opening_state_notification_does_not_create_binary_sensors(
    hass: HomeAssistant,
    client,
    hoppe_ehandle_connectsense_state,
) -> None:
    """Test Opening state does not fan out into per-state binary sensors."""
    # The eHandle fixture has a Binary Sensor CC value for tilt, which we
    # want to ignore in the assertion below
    state = copy.deepcopy(hoppe_ehandle_connectsense_state)
    state["values"] = [
        v
        for v in state["values"]
        if v.get("commandClass") != 48  # Binary Sensor CC
    ]
    node = Node(client, state)
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.states.async_all("binary_sensor")


async def test_opening_state_disables_legacy_window_door_notification_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    hoppe_ehandle_connectsense_state,
) -> None:
    """Test Opening state disables legacy Access Control window/door sensors."""
    node = Node(
        client,
        _add_door_tilt_state_value(hoppe_ehandle_connectsense_state),
    )
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "binary_sensor"
        and entry.platform == "zwave_js"
        and (
            entry.original_name
            in {
                "Window/door is open",
                "Window/door is closed",
                "Window/door is open in regular position",
                "Window/door is open in tilt position",
            }
            or (
                entry.original_name == "Window/door is tilted"
                and entry.original_device_class != BinarySensorDeviceClass.WINDOW
            )
        )
    ]

    assert len(legacy_entries) == 7
    assert all(
        entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for entry in legacy_entries
    )
    assert all(hass.states.get(entry.entity_id) is None for entry in legacy_entries)


async def test_reenabled_legacy_door_state_entity_follows_opening_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    hoppe_ehandle_connectsense_state,
) -> None:
    """Test a re-enabled legacy Door state entity derives state from Opening state."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_entry = next(
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "zwave_js"
        and entry.original_name == "Window/door is open in tilt position"
    )

    entity_registry.async_update_entity(legacy_entry.entity_id, disabled_by=None)
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    state = hass.states.get(legacy_entry.entity_id)
    assert state
    assert state.state == STATE_OFF

    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Notification",
                    "commandClass": 113,
                    "endpoint": 0,
                    "property": "Access Control",
                    "propertyKey": "Opening state",
                    "newValue": 2,
                    "prevValue": 0,
                    "propertyName": "Access Control",
                    "propertyKeyName": "Opening state",
                },
            },
        )
    )

    state = hass.states.get(legacy_entry.entity_id)
    assert state
    assert state.state == STATE_ON


async def test_legacy_door_state_entities_follow_opening_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    hoppe_ehandle_connectsense_state,
) -> None:
    """Test all legacy door state entities correctly derive state from Opening state."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Re-enable all 6 legacy door state entities.
    legacy_names = {
        "Window/door is open",
        "Window/door is closed",
        "Window/door is open in regular position",
        "Window/door is open in tilt position",
    }
    legacy_entries = [
        e
        for e in entity_registry.entities.values()
        if e.domain == "binary_sensor"
        and e.platform == "zwave_js"
        and e.original_name in legacy_names
    ]
    assert len(legacy_entries) == 6
    for legacy_entry in legacy_entries:
        entity_registry.async_update_entity(legacy_entry.entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # With Opening state = 0 (Closed), all "open" entities should be OFF and
    # all "closed" entities should be ON.
    open_entries = [
        e for e in legacy_entries if e.original_name == "Window/door is open"
    ]
    closed_entries = [
        e for e in legacy_entries if e.original_name == "Window/door is closed"
    ]
    open_regular_entries = [
        e
        for e in legacy_entries
        if e.original_name == "Window/door is open in regular position"
    ]
    open_tilt_entries = [
        e
        for e in legacy_entries
        if e.original_name == "Window/door is open in tilt position"
    ]

    for e in open_entries + open_regular_entries + open_tilt_entries:
        state = hass.states.get(e.entity_id)
        assert state, f"{e.entity_id} should have a state"
        assert state.state == STATE_OFF, (
            f"{e.entity_id} ({e.original_name}) should be OFF when Opening state=Closed"
        )
    for e in closed_entries:
        state = hass.states.get(e.entity_id)
        assert state, f"{e.entity_id} should have a state"
        assert state.state == STATE_ON, (
            f"{e.entity_id} ({e.original_name}) should be ON when Opening state=Closed"
        )

    # Update Opening state to 1 (Open).
    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Notification",
                    "commandClass": 113,
                    "endpoint": 0,
                    "property": "Access Control",
                    "propertyKey": "Opening state",
                    "newValue": 1,
                    "prevValue": 0,
                    "propertyName": "Access Control",
                    "propertyKeyName": "Opening state",
                },
            },
        )
    )
    await hass.async_block_till_done()

    # All "open" entities should now be ON, "closed" OFF, "tilt" OFF.
    for e in open_entries + open_regular_entries:
        state = hass.states.get(e.entity_id)
        assert state, f"{e.entity_id} should have a state"
        assert state.state == STATE_ON, (
            f"{e.entity_id} ({e.original_name}) should be ON when Opening state=Open"
        )
    for e in closed_entries + open_tilt_entries:
        state = hass.states.get(e.entity_id)
        assert state, f"{e.entity_id} should have a state"
        assert state.state == STATE_OFF, (
            f"{e.entity_id} ({e.original_name}) should be OFF when Opening state=Open"
        )


async def test_legacy_door_state_non_zero_endpoint(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    hoppe_ehandle_connectsense_state: NodeDataType,
) -> None:
    """Test legacy door state entities work when notification values are on endpoint 1.

    Regression test for https://github.com/home-assistant/core/issues/166365.
    """
    state = _move_notification_values_to_endpoint(
        hoppe_ehandle_connectsense_state, endpoint=1
    )
    node = Node(client, state)
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Legacy door state entities should still be discovered and disabled by default
    # (because the Opening state value exists on the same endpoint).
    legacy_names = {
        "Window/door is open",
        "Window/door is closed",
        "Window/door is open in regular position",
        "Window/door is open in tilt position",
    }
    legacy_entries = [
        e
        for e in entity_registry.entities.values()
        if e.domain == "binary_sensor"
        and e.platform == "zwave_js"
        and e.original_name in legacy_names
    ]
    assert len(legacy_entries) == 6

    # Re-enable them to verify they can be initialized without errors.
    for legacy_entry in legacy_entries:
        entity_registry.async_update_entity(legacy_entry.entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # All entities should have a valid state (no assertion errors during init).
    for e in legacy_entries:
        state = hass.states.get(e.entity_id)
        assert state is not None, f"{e.entity_id} should have a state"
        assert state.state != STATE_UNKNOWN, (
            f"{e.entity_id} ({e.original_name}) should not be unknown"
        )


async def test_access_control_lock_state_notification_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    lock_august_asl03_state,
) -> None:
    """Test Access Control lock state notification sensors from new discovery schemas."""
    node = Node(client, _add_lock_state_notification_states(lock_august_asl03_state))
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    lock_state_entities = [
        state
        for state in hass.states.async_all("binary_sensor")
        if state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.LOCK
    ]
    assert len(lock_state_entities) == 4
    assert all(state.state == STATE_OFF for state in lock_state_entities)

    jammed_entry = next(
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "binary_sensor"
        and entry.platform == "zwave_js"
        and entry.original_name == "Lock jammed"
    )
    assert jammed_entry.original_device_class == BinarySensorDeviceClass.PROBLEM
    assert jammed_entry.entity_category == EntityCategory.DIAGNOSTIC

    jammed_state = hass.states.get(jammed_entry.entity_id)
    assert jammed_state
    assert jammed_state.state == STATE_OFF


async def test_access_control_catch_all_with_opening_state_present(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    hoppe_ehandle_connectsense_state,
) -> None:
    """Test that unrelated Access Control values are discovered even when Opening state is present."""
    node = Node(
        client,
        _add_barrier_status_value(hoppe_ehandle_connectsense_state),
    )
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The two non-idle barrier states should each become a diagnostic binary sensor
    barrier_entries = [
        reg_entry
        for reg_entry in entity_registry.entities.values()
        if reg_entry.domain == "binary_sensor"
        and reg_entry.platform == "zwave_js"
        and reg_entry.entity_category == EntityCategory.DIAGNOSTIC
        and reg_entry.original_name
        and "barrier" in reg_entry.original_name.lower()
    ]
    assert len(barrier_entries) == 2, (
        f"Expected 2 barrier status sensors, got {[e.original_name for e in barrier_entries]}"
    )
    for reg_entry in barrier_entries:
        state = hass.states.get(reg_entry.entity_id)
        assert state is not None
        assert state.state == STATE_OFF


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

    # Test that no idle states are created as entities
    entity_id = "binary_sensor.zcombo_g_smoke_co_alarm_idle"
    state = hass.states.get(entity_id)
    assert state is None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is None

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


async def test_hoppe_ehandle_connectsense(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hoppe_ehandle_connectsense: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Hoppe eHandle ConnectSense tilt sensor is discovered as a window sensor."""
    entity_id = "binary_sensor.ehandle_connectsense_window_door_is_tilted"
    state = hass.states.get(entity_id)
    assert state is not None, (
        "Window/door is tilted sensor should be enabled by default"
    )
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.original_name == "Window/door is tilted"
    assert entry.original_device_class == BinarySensorDeviceClass.WINDOW
    assert entry.disabled_by is None, "Entity should be enabled by default"


async def test_legacy_door_state_repair_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    hoppe_ehandle_connectsense_state: NodeDataType,
) -> None:
    """Test repair issue is created only when legacy door state entity is in automation."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node
    home_id = client.driver.controller.home_id

    # Pre-register the legacy entity as enabled (simulating existing user entity).
    unique_id = f"{home_id}.20-113-0-Access Control-Door state.22"
    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id="ehandle_connectsense_window_door_is_open",
        original_name="Window/door is open",
    )
    entity_id = entity_entry.entity_id

    # Load the integration without any automation referencing the entity.
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No repair issues should exist without automations.
    issues = [
        issue
        for issue in issue_registry.issues.values()
        if issue.domain == DOMAIN
        and issue.translation_key == "deprecated_legacy_door_state"
    ]
    assert len(issues) == 0

    # Now set up an automation referencing the legacy entity.
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test_automation",
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {"entity_id": "automation.test_automation"},
                },
            }
        },
    )

    # Reload the integration so the repair check runs again.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_legacy_door_state.{entity_id}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_legacy_door_state"
    assert issue.translation_placeholders["entity_id"] == entity_id
    assert issue.translation_placeholders["entity_name"] == "Window/door is open"
    assert (
        issue.translation_placeholders["opening_state_entity_id"]
        == "sensor.ehandle_connectsense_opening_state"
    )
    assert "test" in issue.translation_placeholders["items"]


async def test_legacy_door_state_no_repair_issue_when_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    hoppe_ehandle_connectsense_state: NodeDataType,
) -> None:
    """Test no repair issue when legacy door state entity is disabled."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node
    home_id = client.driver.controller.home_id

    # Pre-register the legacy entity as disabled.
    unique_id = f"{home_id}.20-113-0-Access Control-Door state.22"
    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id="ehandle_connectsense_window_door_is_open",
        original_name="Window/door is open",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    entity_id = entity_entry.entity_id
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test_automation",
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {"entity_id": "automation.test_automation"},
                },
            }
        },
    )

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No repair issue should be created since the entity is disabled.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_legacy_door_state.{entity_id}"
    )
    assert issue is None


async def test_hoppe_custom_tilt_sensor_no_repair_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    hoppe_ehandle_connectsense_state: NodeDataType,
) -> None:
    """Test no repair issue for Hoppe eHandle custom tilt sensor (Binary Sensor CC)."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node

    # Pre-register the Hoppe tilt entity as enabled (simulating existing user entity).
    home_id = client.driver.controller.home_id
    unique_id = f"{home_id}.20-48-0-Tilt"
    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id="ehandle_connectsense_window_door_is_tilted",
        original_name="Window/door is tilted",
    )
    entity_id = entity_entry.entity_id

    # Set up automation referencing the custom tilt entity.
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test_automation",
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {"entity_id": "automation.test_automation"},
                },
            }
        },
    )

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No repair issue should be created - this is a custom Binary Sensor CC entity,
    # not a legacy Notification CC door state entity.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_legacy_door_state.{entity_id}"
    )
    assert issue is None


async def test_legacy_door_state_stale_repair_issue_cleaned_up(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    hoppe_ehandle_connectsense_state: NodeDataType,
) -> None:
    """Test that a stale repair issue is deleted when there are no automations."""
    node = Node(client, hoppe_ehandle_connectsense_state)
    client.driver.controller.nodes[node.node_id] = node
    home_id = client.driver.controller.home_id

    # Pre-register the legacy entity as enabled.
    unique_id = f"{home_id}.20-113-0-Access Control-Door state.22"
    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id="ehandle_connectsense_window_door_is_open",
        original_name="Window/door is open",
    )
    entity_id = entity_entry.entity_id

    # Seed a stale repair issue as if it had been created in a previous run.
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_legacy_door_state.{entity_id}",
        is_fixable=False,
        is_persistent=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_legacy_door_state",
        translation_placeholders={
            "entity_id": entity_id,
            "entity_name": "Window/door is open",
            "opening_state_entity_id": "sensor.ehandle_connectsense_opening_state",
            "items": "- [test](/config/automation/edit/test_automation)",
        },
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"deprecated_legacy_door_state.{entity_id}"
        )
        is not None
    )

    # Load the integration with no automation referencing the legacy entity.
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Stale issue should have been cleaned up.
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"deprecated_legacy_door_state.{entity_id}"
        )
        is None
    )
