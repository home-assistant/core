"""The tests for Z-Wave JS automation triggers."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
import copy
from typing import Any
from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node, NodeDataType

from homeassistant.components import automation
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import (
    async_bypass_dynamic_config_validation,
    get_device_id,
    get_endpoint_device_id,
)
from homeassistant.components.zwave_js.trigger import TRIGGERS
from homeassistant.components.zwave_js.triggers.event import (
    _OPTIONS_SCHEMA_DICT as EVENT_OPTIONS_SCHEMA_DICT,
)
from homeassistant.components.zwave_js.triggers.value_updated import (
    _OPTIONS_SCHEMA_DICT as VALUE_UPDATED_OPTIONS_SCHEMA_DICT,
    async_attach_trigger as async_attach_value_updated_trigger,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import MATCH_ALL, SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, trigger
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component

from .common import COMMAND_CLASS_MARKERS, SCHLAGE_BE469_LOCK_ENTITY


async def test_zwave_js_value_updated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469,
    integration,
) -> None:
    """Test for zwave_js.value_updated automation trigger."""
    trigger_type = f"{DOMAIN}.value_updated"
    node: Node = lock_schlage_be469
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device

    no_value_filter = async_capture_events(hass, "no_value_filter")
    single_from_value_filter = async_capture_events(hass, "single_from_value_filter")
    multiple_from_value_filters = async_capture_events(
        hass, "multiple_from_value_filters"
    )
    from_and_to_value_filters = async_capture_events(hass, "from_and_to_value_filters")
    different_value = async_capture_events(hass, "different_value")

    def clear_events():
        """Clear all events in the event list."""
        no_value_filter.clear()
        single_from_value_filter.clear()
        multiple_from_value_filters.clear()
        from_and_to_value_filters.clear()
        different_value.clear()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # no value filter
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                        },
                    },
                    "action": {
                        "event": "no_value_filter",
                    },
                },
                # single from value filter
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": device.id,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                            "from": "ajar",
                        },
                    },
                    "action": {
                        "event": "single_from_value_filter",
                    },
                },
                # multiple from value filters
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                            "from": ["closed", "opened"],
                        },
                    },
                    "action": {
                        "event": "multiple_from_value_filters",
                    },
                },
                # from and to value filters
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                            "from": ["closed", "opened"],
                            "to": ["opened"],
                        },
                    },
                    "action": {
                        "event": "from_and_to_value_filters",
                    },
                },
                # different value
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "boltStatus",
                        },
                    },
                    "action": {
                        "event": "different_value",
                    },
                },
            ]
        },
    )

    # Test that no value filter is triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1
    assert len(single_from_value_filter) == 0
    assert len(multiple_from_value_filters) == 0
    assert len(from_and_to_value_filters) == 0
    assert len(different_value) == 0

    clear_events()

    # Test that a single_from_value_filter is triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "ajar",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1
    assert len(single_from_value_filter) == 1
    assert len(multiple_from_value_filters) == 0
    assert len(from_and_to_value_filters) == 0
    assert len(different_value) == 0

    clear_events()

    # Test that multiple_from_value_filters are triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "closed",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1
    assert len(single_from_value_filter) == 0
    assert len(multiple_from_value_filters) == 1
    assert len(from_and_to_value_filters) == 0
    assert len(different_value) == 0

    clear_events()

    # Test that from_and_to_value_filters is triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "opened",
                "prevValue": "closed",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1
    assert len(single_from_value_filter) == 0
    assert len(multiple_from_value_filters) == 1
    assert len(from_and_to_value_filters) == 1
    assert len(different_value) == 0

    clear_events()

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "boltStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "boltStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 0
    assert len(single_from_value_filter) == 0
    assert len(multiple_from_value_filters) == 0
    assert len(from_and_to_value_filters) == 0
    assert len(different_value) == 1

    clear_events()

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)


async def test_zwave_js_value_updated_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the value_updated trigger reports the targeted endpoint child device id."""
    trigger_type = f"{DOMAIN}.value_updated"
    node = climate_heatit_z_trm3
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    child_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert child_device

    child_events = async_capture_events(hass, "child_device_trigger")
    node_events = async_capture_events(hass, "node_device_trigger")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": child_device.id,
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 2,
                        },
                    },
                    "action": {
                        "event": "child_device_trigger",
                        "event_data": {"device_id": "{{ trigger.device_id }}"},
                    },
                },
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": node_device.id,
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 2,
                        },
                    },
                    "action": {
                        "event": "node_device_trigger",
                        "event_data": {"device_id": "{{ trigger.device_id }}"},
                    },
                },
            ]
        },
    )

    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )
    )
    await hass.async_block_till_done()

    # The child-targeted trigger reports the child device, while the node-targeted trigger
    # reports the parent node device even though the value lives on the child endpoint.
    assert len(child_events) == 1
    assert child_events[0].data["device_id"] == child_device.id
    assert len(node_events) == 1
    assert node_events[0].data["device_id"] == node_device.id


async def test_zwave_js_value_updated_child_device_endpoint_validation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a child-device value_updated trigger validates the configured endpoint.

    A child device still resolves to its node, so an omitted or mismatched endpoint
    would otherwise validate but silently attach no listener.
    """
    node = climate_heatit_z_trm3
    child_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert child_device

    def make_config(options: dict[str, Any]) -> dict[str, Any]:
        return {
            "platform": f"{DOMAIN}.value_updated",
            "options": {
                "device_id": child_device.id,
                "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                "property": "Air temperature",
                **options,
            },
        }

    # The endpoint the child device covers validates.
    assert await TRIGGERS["value_updated"].async_validate_complete_config(
        hass, make_config({"endpoint": 2})
    )

    # An omitted endpoint is rejected.
    with pytest.raises(
        probatio.Invalid, match="not covered by any targeted endpoint child device"
    ):
        await TRIGGERS["value_updated"].async_validate_complete_config(
            hass, make_config({})
        )

    # An endpoint the child device does not cover is rejected.
    with pytest.raises(
        probatio.Invalid, match="not covered by any targeted endpoint child device"
    ):
        await TRIGGERS["value_updated"].async_validate_complete_config(
            hass, make_config({"endpoint": 3})
        )


async def test_zwave_js_value_updated_child_device_endpoint_mismatch_warns(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attaching a child trigger with an uncovered endpoint drops it with a warning.

    Validation rejects this up front, but attaching must still drop the target (rather
    than attach a listener on an unrelated endpoint) and warn, e.g. when the child's
    endpoints changed after the automation was created.
    """
    node = climate_heatit_z_trm3
    child_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert child_device

    events: list[dict[str, Any]] = []
    unsub = await async_attach_value_updated_trigger(
        hass,
        {
            "device_id": [child_device.id],
            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
            "property": "Air temperature",
            "endpoint": 3,  # the endpoint 2 child device does not cover endpoint 3
            "from": MATCH_ALL,
            "to": MATCH_ALL,
        },
        lambda payload, description=None: events.append(payload),
    )

    assert "does not cover endpoint 3" in caplog.text

    # No listener was attached, so a value update produces no trigger.
    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )
    )
    await hass.async_block_till_done()
    assert not events

    unsub()


async def test_zwave_js_value_updated_child_device_unavailable_target(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    aeotec_zwa046: Node,
    integration: MockConfigEntry,
) -> None:
    """Test attachment continues for a reachable child target when another is unavailable.

    A value_updated trigger can target multiple child devices. If one target's node can't
    be resolved (unloaded entry, unavailable driver), the reachable targets must still
    attach instead of the whole trigger aborting.
    """
    trigger_type = f"{DOMAIN}.value_updated"
    reachable_node = climate_heatit_z_trm3
    reachable_child = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(
            client.driver, reachable_node, reachable_node.endpoints[2]
        ),
        integration.entry_id,
    )
    assert reachable_child
    unavailable_child = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(
            client.driver, aeotec_zwa046, aeotec_zwa046.endpoint_groups[1]
        ),
        integration.entry_id,
    )
    assert unavailable_child

    # Make the second target's node unresolvable, as if its driver became unavailable.
    del client.driver.controller.nodes[aeotec_zwa046.node_id]

    events = async_capture_events(hass, "child_trigger")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": [reachable_child.id, unavailable_child.id],
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 2,
                        },
                    },
                    "action": {
                        "event": "child_trigger",
                        "event_data": {"device_id": "{{ trigger.device_id }}"},
                    },
                },
            ]
        },
    )

    reachable_node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": reachable_node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )
    )
    await hass.async_block_till_done()

    # The reachable child target still attached and fired, reporting its child device id.
    assert len(events) == 1
    assert events[0].data["device_id"] == reachable_child.id


async def test_zwave_js_value_updated_multiple_child_targets(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the child covering the configured endpoint is reported with several targets.

    A node collapses to a single listener, so when two child devices of the same node are
    targeted the child covering the configured endpoint must be reported, not whichever
    target happens to be processed last.
    """
    trigger_type = f"{DOMAIN}.value_updated"
    node = climate_heatit_z_trm3
    room_child = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    external_child = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[3]),
        integration.entry_id,
    )
    assert room_child
    assert external_child

    events = async_capture_events(hass, "child_trigger")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            # The endpoint 3 child is listed last, so without selecting by
                            # endpoint it would overwrite the endpoint 2 child's mapping.
                            "device_id": [room_child.id, external_child.id],
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 2,
                        },
                    },
                    "action": {
                        "event": "child_trigger",
                        "event_data": {"device_id": "{{ trigger.device_id }}"},
                    },
                },
            ]
        },
    )

    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )
    )
    await hass.async_block_till_done()

    # The endpoint 2 update reports the endpoint 2 child device, not the endpoint 3 one.
    assert len(events) == 1
    assert events[0].data["device_id"] == room_child.id


async def test_zwave_js_value_updated_child_devices_across_networks(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    climate_heatit_z_trm3_state: NodeDataType,
    controller_state: dict[str, Any],
    log_config_state: dict[str, Any],
    integration: MockConfigEntry,
) -> None:
    """Test cross-network child targets report their own network's device.

    Two Z-Wave networks can have nodes that share a node id. A value-updated trigger that
    targets an endpoint child device on each network with the same endpoint must report
    the child device of the network whose value actually updated, not whichever target
    was processed last.
    """
    trigger_type = f"{DOMAIN}.value_updated"

    # Network 1 is the heatit node from the integration fixture.
    node1 = climate_heatit_z_trm3
    child1 = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node1, node1.endpoints[2]),
        integration.entry_id,
    )
    assert child1

    # Network 2 is a second driver with a different home id, hosting a node that reuses
    # the same node id and also has an endpoint 2 child device.
    controller2_state = copy.deepcopy(controller_state)
    controller2_state["controller"]["homeId"] = (
        controller_state["controller"]["homeId"] + 1
    )
    client2 = MagicMock()
    client2.driver = Driver(client2, controller2_state, copy.deepcopy(log_config_state))
    node2 = Node(client2, copy.deepcopy(climate_heatit_z_trm3_state))
    client2.driver.controller.nodes[node2.node_id] = node2
    assert node2.node_id == node1.node_id

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://test2.org"},
        unique_id=str(client2.driver.controller.home_id),
        state=ConfigEntryState.LOADED,
    )
    entry2.add_to_hass(hass)
    entry2.runtime_data = MagicMock(client=client2)
    parent2 = device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={get_device_id(client2.driver, node2)},
    )
    child2 = device_registry.async_get_or_create_child(
        config_entry_id=entry2.entry_id,
        identifiers={get_endpoint_device_id(client2.driver, node2, node2.endpoints[2])},
        parent_device_id=parent2.id,
    )
    assert child2.id != child1.id

    events = async_capture_events(hass, "child_trigger")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            # Network 2's child is listed last, so a node-id-only key
                            # would overwrite network 1's mapping.
                            "device_id": [child1.id, child2.id],
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 2,
                        },
                    },
                    "action": {
                        "event": "child_trigger",
                        "event_data": {"device_id": "{{ trigger.device_id }}"},
                    },
                },
            ]
        },
    )

    def _value_updated_event(node: Node) -> Event:
        return Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )

    # A value update on network 1 reports network 1's child device.
    node1.receive_event(_value_updated_event(node1))
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["device_id"] == child1.id

    # A value update on network 2 reports network 2's child device.
    node2.receive_event(_value_updated_event(node2))
    await hass.async_block_till_done()
    assert len(events) == 2
    assert events[1].data["device_id"] == child2.id


async def test_zwave_js_value_updated_child_device_endpoint_mismatch(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a child target that does not cover the configured endpoint does not attach.

    A trigger targeting only the endpoint 2 child device with endpoint 3 must not fall
    back to a node listener on endpoint 3, which would fire for an unrelated endpoint.
    """
    trigger_type = f"{DOMAIN}.value_updated"
    node = climate_heatit_z_trm3
    room_child = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert room_child

    events = async_capture_events(hass, "child_trigger")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": [room_child.id],
                            "command_class": CommandClass.SENSOR_MULTILEVEL.value,
                            "property": "Air temperature",
                            "endpoint": 3,
                        },
                    },
                    "action": {"event": "child_trigger"},
                },
            ]
        },
    )

    node.receive_event(
        Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 3,
                    "property": "Air temperature",
                    "propertyName": "Air temperature",
                    "newValue": 25.5,
                    "prevValue": 20.0,
                },
            },
        )
    )
    await hass.async_block_till_done()

    # The endpoint 2 child does not cover endpoint 3, so no listener attached and the
    # endpoint 3 update does not fire.
    assert len(events) == 0


async def test_zwave_js_value_updated_bypass_dynamic_validation(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test zwave_js.value_updated trigger when bypassing dynamic validation."""
    trigger_type = f"{DOMAIN}.value_updated"
    node: Node = lock_schlage_be469

    no_value_filter = async_capture_events(hass, "no_value_filter")

    with patch(
        "homeassistant.components.zwave_js.triggers.value_updated.async_bypass_dynamic_config_validation",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    # no value filter
                    {
                        "trigger": {
                            "platform": trigger_type,
                            "options": {
                                "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                                "command_class": CommandClass.DOOR_LOCK.value,
                                "property": "latchStatus",
                            },
                        },
                        "action": {
                            "event": "no_value_filter",
                        },
                    },
                ]
            },
        )

    # Test that no value filter is triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1


async def test_zwave_js_value_updated_bypass_dynamic_validation_no_nodes(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test value_updated trigger when bypassing dynamic validation with no nodes."""
    trigger_type = f"{DOMAIN}.value_updated"
    node: Node = lock_schlage_be469

    no_value_filter = async_capture_events(hass, "no_value_filter")

    with patch(
        "homeassistant.components.zwave_js.triggers.value_updated.async_bypass_dynamic_config_validation",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    # no value filter
                    {
                        "trigger": {
                            "platform": trigger_type,
                            "options": {
                                "entity_id": "sensor.test",
                                "command_class": CommandClass.DOOR_LOCK.value,
                                "property": "latchStatus",
                            },
                        },
                        "action": {
                            "event": "no_value_filter",
                        },
                    },
                ]
            },
        )

    # Test that no value filter is NOT triggered because automation failed setup
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 0


async def test_zwave_js_value_updated_bypass_dynamic_validation_no_driver(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test zwave_js.value_updated trigger without driver."""
    trigger_type = f"{DOMAIN}.value_updated"
    node: Node = lock_schlage_be469
    driver = client.driver
    client.driver = None

    no_value_filter = async_capture_events(hass, "no_value_filter")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # no value filter
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                        },
                    },
                    "action": {
                        "event": "no_value_filter",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    client.driver = driver

    # Test that no value filter is NOT triggered because automation failed setup
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 0


async def test_zwave_js_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469,
    integration,
) -> None:
    """Test for zwave_js.event automation trigger."""
    trigger_type = f"{DOMAIN}.event"
    node: Node = lock_schlage_be469
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device

    node_no_event_data_filter = async_capture_events(hass, "node_no_event_data_filter")
    node_event_data_filter = async_capture_events(hass, "node_event_data_filter")
    controller_no_event_data_filter = async_capture_events(
        hass, "controller_no_event_data_filter"
    )
    controller_event_data_filter = async_capture_events(
        hass, "controller_event_data_filter"
    )
    driver_no_event_data_filter = async_capture_events(
        hass, "driver_no_event_data_filter"
    )
    driver_event_data_filter = async_capture_events(hass, "driver_event_data_filter")
    node_event_data_no_partial_dict_match_filter = async_capture_events(
        hass, "node_event_data_no_partial_dict_match_filter"
    )
    node_event_data_partial_dict_match_filter = async_capture_events(
        hass, "node_event_data_partial_dict_match_filter"
    )

    def clear_events():
        """Clear all events in the event list."""
        node_no_event_data_filter.clear()
        node_event_data_filter.clear()
        controller_no_event_data_filter.clear()
        controller_event_data_filter.clear()
        driver_no_event_data_filter.clear()
        driver_event_data_filter.clear()
        node_event_data_no_partial_dict_match_filter.clear()
        node_event_data_partial_dict_match_filter.clear()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # node filter: no event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "event_source": "node",
                            "event": "interview stage completed",
                        },
                    },
                    "action": {
                        "event": "node_no_event_data_filter",
                    },
                },
                # node filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "device_id": device.id,
                            "event_source": "node",
                            "event": "interview stage completed",
                            "event_data": {"stageName": "ProtocolInfo"},
                        },
                    },
                    "action": {
                        "event": "node_event_data_filter",
                    },
                },
                # controller filter: no event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "config_entry_id": integration.entry_id,
                            "event_source": "controller",
                            "event": "inclusion started",
                        },
                    },
                    "action": {
                        "event": "controller_no_event_data_filter",
                    },
                },
                # controller filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "config_entry_id": integration.entry_id,
                            "event_source": "controller",
                            "event": "inclusion started",
                            "event_data": {"strategy": 0},
                        },
                    },
                    "action": {
                        "event": "controller_event_data_filter",
                    },
                },
                # driver filter: no event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "config_entry_id": integration.entry_id,
                            "event_source": "driver",
                            "event": "logging",
                        },
                    },
                    "action": {
                        "event": "driver_no_event_data_filter",
                    },
                },
                # driver filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "config_entry_id": integration.entry_id,
                            "event_source": "driver",
                            "event": "logging",
                            "event_data": {"message": "test"},
                        },
                    },
                    "action": {
                        "event": "driver_event_data_filter",
                    },
                },
                # node filter: event data, no partial dict match
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "event_source": "node",
                            "event": "value updated",
                            "event_data": {"args": {"commandClassName": "Door Lock"}},
                        },
                    },
                    "action": {
                        "event": "node_event_data_no_partial_dict_match_filter",
                    },
                },
                # node filter: event data, partial dict match
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "event_source": "node",
                            "event": "value updated",
                            "event_data": {"args": {"commandClassName": "Door Lock"}},
                            "partial_dict_match": True,
                        },
                    },
                    "action": {
                        "event": "node_event_data_partial_dict_match_filter",
                    },
                },
            ]
        },
    )

    # Test that `node no event data filter` is triggered and `node event data
    # filter` is not
    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 1
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that `node no event data filter` and `node event data filter` are triggered
    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "ProtocolInfo",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 1
    assert len(node_event_data_filter) == 1
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that `controller no event data filter` is triggered and `controller event
    # data filter` is not
    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "strategy": 2,
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 1
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that both `controller no event data filter` and `controller event data
    # filter`` are triggered
    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "strategy": 0,
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 1
    assert len(controller_event_data_filter) == 1
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that `driver no event data filter` is triggered and `driver event data
    # filter` is not
    event = Event(
        type="logging",
        data={
            "source": "driver",
            "event": "logging",
            "message": "no test",
            "formattedMessage": "test",
            "direction": ">",
            "level": "debug",
            "primaryTags": "tag",
            "secondaryTags": "tag2",
            "secondaryTagPadding": 0,
            "multiline": False,
            "timestamp": "time",
            "label": "label",
            "context": {"source": "config"},
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 1
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that both `driver no event data filter` and `driver event data filter`
    # are triggered
    event = Event(
        type="logging",
        data={
            "source": "driver",
            "event": "logging",
            "message": "test",
            "formattedMessage": "test",
            "direction": ">",
            "level": "debug",
            "primaryTags": "tag",
            "secondaryTags": "tag2",
            "secondaryTagPadding": 0,
            "multiline": False,
            "timestamp": "time",
            "label": "label",
            "context": {"source": "config"},
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 1
    assert len(driver_event_data_filter) == 1
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    # Test that only `node with event data and partial match dict filter` is triggered
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 49,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "closed",
                "prevValue": "open",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 1

    clear_events()

    # Test that `node with event data and partial match dict filter` is not triggered
    # when partial dict doesn't match
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "fake command class name",
                "commandClass": 49,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "closed",
                "prevValue": "open",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0
    assert len(node_event_data_filter) == 0
    assert len(controller_no_event_data_filter) == 0
    assert len(controller_event_data_filter) == 0
    assert len(driver_no_event_data_filter) == 0
    assert len(driver_event_data_filter) == 0
    assert len(node_event_data_no_partial_dict_match_filter) == 0
    assert len(node_event_data_partial_dict_match_filter) == 0

    clear_events()

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)


async def test_zwave_js_event_bypass_dynamic_validation(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test zwave_js.event trigger when bypassing dynamic config validation."""
    trigger_type = f"{DOMAIN}.event"
    node: Node = lock_schlage_be469

    node_no_event_data_filter = async_capture_events(hass, "node_no_event_data_filter")

    with patch(
        "homeassistant.components.zwave_js.triggers.event.async_bypass_dynamic_config_validation",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    # node filter: no event data
                    {
                        "trigger": {
                            "platform": trigger_type,
                            "options": {
                                "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                                "event_source": "node",
                                "event": "interview stage completed",
                            },
                        },
                        "action": {
                            "event": "node_no_event_data_filter",
                        },
                    },
                ]
            },
        )

    # Test that `node no event data filter` is triggered and `node event data filter`
    # is not
    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 1


async def test_zwave_js_event_bypass_dynamic_validation_no_nodes(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test event trigger when bypassing dynamic validation with no nodes."""
    trigger_type = f"{DOMAIN}.event"
    node: Node = lock_schlage_be469

    node_no_event_data_filter = async_capture_events(hass, "node_no_event_data_filter")

    with patch(
        "homeassistant.components.zwave_js.triggers.event.async_bypass_dynamic_config_validation",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    # node filter: no event data
                    {
                        "trigger": {
                            "platform": trigger_type,
                            "options": {
                                "entity_id": "sensor.fake",
                                "event_source": "node",
                                "event": "interview stage completed",
                            },
                        },
                        "action": {
                            "event": "node_no_event_data_filter",
                        },
                    },
                ]
            },
        )

    # Test that `node no event data filter` is NOT triggered because automation failed
    # setup
    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    assert len(node_no_event_data_filter) == 0


async def test_zwave_js_event_invalid_config_entry_id(
    hass: HomeAssistant, client, integration, caplog: pytest.LogCaptureFixture
) -> None:
    """Test zwave_js.event automation trigger fails when config entry ID is invalid."""
    trigger_type = f"{DOMAIN}.event"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "config_entry_id": "not_real_entry_id",
                            "event_source": "controller",
                            "event": "inclusion started",
                        },
                    },
                    "action": {
                        "event": "node_no_event_data_filter",
                    },
                }
            ]
        },
    )

    assert "Config entry 'not_real_entry_id' not found" in caplog.text
    caplog.clear()


async def test_invalid_trigger_configs(hass: HomeAssistant) -> None:
    """Test invalid trigger configs."""
    with pytest.raises(probatio.Invalid):
        await TRIGGERS["event"].async_validate_complete_config(
            hass,
            {
                "platform": f"{DOMAIN}.event",
                "options": {
                    "entity_id": "fake.entity",
                    "event_source": "node",
                    "event": "value updated",
                },
            },
        )

    with pytest.raises(probatio.Invalid):
        await TRIGGERS["value_updated"].async_validate_complete_config(
            hass,
            {
                "platform": f"{DOMAIN}.value_updated",
                "options": {
                    "entity_id": "fake.entity",
                    "command_class": CommandClass.DOOR_LOCK.value,
                    "property": "latchStatus",
                },
            },
        )


@pytest.mark.parametrize(
    ("event_source", "event", "option_keys", "expectation"),
    [
        pytest.param(
            "controller",
            "inclusion started",
            ["config_entry_id", "device_id"],
            pytest.raises(probatio.Invalid, match="must not contain"),
            id="controller_with_device_id",
        ),
        pytest.param(
            "driver",
            "logging",
            ["config_entry_id", "entity_id"],
            pytest.raises(probatio.Invalid, match="must not contain"),
            id="driver_with_entity_id",
        ),
        pytest.param(
            "node",
            "interview stage completed",
            [],
            pytest.raises(probatio.Invalid, match="must contain"),
            id="node_without_targets",
        ),
        pytest.param(
            "controller",
            "inclusion started",
            ["config_entry_id"],
            does_not_raise(),
            id="controller_without_targets",
        ),
        pytest.param(
            "controller",
            "inclusion started",
            [],
            pytest.raises(probatio.Invalid, match="must contain config_entry_id"),
            id="controller_without_config_entry",
        ),
    ],
)
async def test_zwave_js_event_source_target_validation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    event_source: str,
    event: str,
    option_keys: list[str],
    expectation: AbstractContextManager,
) -> None:
    """Test that zwave_js.event targets are validated against the event source."""
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device
    options = {
        "config_entry_id": integration.entry_id,
        "device_id": device.id,
        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
    }

    with expectation:
        await trigger.async_validate_trigger_config(
            hass,
            [
                {
                    "platform": f"{DOMAIN}.event",
                    "options": {
                        "event_source": event_source,
                        "event": event,
                        **{key: options[key] for key in option_keys},
                    },
                }
            ],
        )


async def test_zwave_js_trigger_config_entry_unloaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469,
    integration,
) -> None:
    """Test zwave_js triggers bypass dynamic validation when needed."""
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device

    # Test bypass check is False
    assert not async_bypass_dynamic_config_validation(
        hass,
        {
            "entity_id": [SCHLAGE_BE469_LOCK_ENTITY],
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
        },
    )

    await hass.config_entries.async_unload(integration.entry_id)

    # Test full validation for both events
    assert await TRIGGERS["value_updated"].async_validate_complete_config(
        hass,
        {
            "platform": f"{DOMAIN}.value_updated",
            "options": {
                "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                "command_class": CommandClass.DOOR_LOCK.value,
                "property": "latchStatus",
            },
        },
    )

    assert await TRIGGERS["event"].async_validate_complete_config(
        hass,
        {
            "platform": f"{DOMAIN}.event",
            "options": {
                "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                "event_source": "node",
                "event": "interview stage completed",
            },
        },
    )

    # Test bypass check
    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "entity_id": [SCHLAGE_BE469_LOCK_ENTITY],
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "device_id": [device.id],
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
            "from": "ajar",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "entity_id": [SCHLAGE_BE469_LOCK_ENTITY],
            "event_source": "node",
            "event": "interview stage completed",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "device_id": [device.id],
            "event_source": "node",
            "event": "interview stage completed",
            "event_data": {"stageName": "ProtocolInfo"},
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "config_entry_id": integration.entry_id,
            "event_source": "controller",
            "event": "nvm convert progress",
        },
    )


@pytest.mark.parametrize(
    ("config_key", "driver", "expected"),
    [
        pytest.param("loaded_device", MagicMock(), False, id="loaded_device"),
        pytest.param("loaded_entity", MagicMock(), False, id="loaded_entity"),
        pytest.param(
            "loaded_child_device", MagicMock(), False, id="loaded_child_device"
        ),
        pytest.param("unloaded_device", MagicMock(), True, id="unloaded_device"),
        pytest.param(
            "unloaded_child_device", MagicMock(), True, id="unloaded_child_device"
        ),
        pytest.param(
            "unloaded_entry", MagicMock(), True, id="unloaded_config_entry_id"
        ),
        pytest.param("nothing", MagicMock(), False, id="nothing_referenced"),
        pytest.param("loaded_device", None, True, id="loaded_device_driver_not_ready"),
        pytest.param(
            "loaded_child_device",
            None,
            True,
            id="loaded_child_device_driver_not_ready",
        ),
        pytest.param("nothing", None, False, id="nothing_referenced_driver_not_ready"),
    ],
)
async def test_bypass_dynamic_config_validation_scoped(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
    config_key: str,
    driver: MagicMock | None,
    expected: bool,
) -> None:
    """Test the bypass check only considers config entries referenced by the config."""
    lock_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert lock_device
    # An endpoint child device of a loaded entry (its node splits into child devices).
    child_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(
            client.driver, climate_heatit_z_trm3, climate_heatit_z_trm3.endpoints[2]
        ),
        integration.entry_id,
    )
    assert child_device

    other_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://test2.org"}, unique_id="other"
    )
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={(DOMAIN, "other-node")}
    )
    # A child device of the unloaded entry, to prove child entries are also considered.
    other_child_device = device_registry.async_get_or_create_child(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "other-child-node")},
        parent_device_id=other_device.id,
    )
    assert other_entry.state is not ConfigEntryState.LOADED

    configs = {
        "loaded_device": {"device_id": [lock_device.id]},
        "loaded_entity": {"entity_id": [SCHLAGE_BE469_LOCK_ENTITY]},
        "loaded_child_device": {"device_id": [child_device.id]},
        "unloaded_device": {"device_id": [other_device.id]},
        "unloaded_child_device": {"device_id": [other_child_device.id]},
        "unloaded_entry": {"config_entry_id": other_entry.entry_id},
        "nothing": {},
    }

    with patch.object(client, "driver", driver):
        assert (
            async_bypass_dynamic_config_validation(hass, configs[config_key])
            is expected
        )


async def test_server_reconnect_event(
    hass: HomeAssistant,
    client,
    lock_schlage_be469,
    lock_schlage_be469_state,
    integration,
) -> None:
    """Test that when we reconnect to server, event triggers reattach."""
    trigger_type = f"{DOMAIN}.event"
    old_node: Node = lock_schlage_be469

    event_name = "interview stage completed"

    old_node = client.driver.controller.nodes[20]

    original_len = len(old_node._listeners.get(event_name, []))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "event_source": "node",
                            "event": event_name,
                        },
                    },
                    "action": {
                        "event": "blah",
                    },
                },
            ]
        },
    )

    assert len(old_node._listeners.get(event_name, [])) == original_len + 1
    old_listener = old_node._listeners.get(event_name, [])[original_len]

    # Remove node so that we can create a new node instance and make sure the listener
    # attaches
    node_removed_event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 0,
            "node": lock_schlage_be469_state,
        },
    )
    client.driver.controller.receive_event(node_removed_event)
    assert 20 not in client.driver.controller.nodes
    await hass.async_block_till_done()

    # Add node like new server connection would
    node_added_event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": lock_schlage_be469_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(node_added_event)
    await hass.async_block_till_done()

    # Reload integration to trigger the dispatch signal
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Make sure there is a listener added for the trigger to the new node
    new_node = client.driver.controller.nodes[20]
    assert len(new_node._listeners.get(event_name, [])) == original_len + 1

    # Make sure the old listener is no longer referenced
    assert old_listener not in new_node._listeners.get(event_name, [])


async def test_server_reconnect_value_updated(
    hass: HomeAssistant,
    client,
    lock_schlage_be469,
    lock_schlage_be469_state,
    integration,
) -> None:
    """Test that when we reconnect to server, value_updated triggers reattach."""
    trigger_type = f"{DOMAIN}.value_updated"
    old_node: Node = lock_schlage_be469

    event_name = "value updated"

    old_node = client.driver.controller.nodes[20]

    original_len = len(old_node._listeners.get(event_name, []))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                        },
                    },
                    "action": {
                        "event": "no_value_filter",
                    },
                },
            ]
        },
    )

    assert len(old_node._listeners.get(event_name, [])) == original_len + 1
    old_listener = old_node._listeners.get(event_name, [])[original_len]

    # Remove node so that we can create a new node instance and make sure the listener
    # attaches
    node_removed_event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 0,
            "node": lock_schlage_be469_state,
        },
    )
    client.driver.controller.receive_event(node_removed_event)
    assert 20 not in client.driver.controller.nodes
    await hass.async_block_till_done()

    # Add node like new server connection would
    node_added_event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": lock_schlage_be469_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(node_added_event)
    await hass.async_block_till_done()

    # Reload integration to trigger the dispatch signal
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Make sure there is a listener added for the trigger to the new node
    new_node = client.driver.controller.nodes[20]
    assert len(new_node._listeners.get(event_name, [])) == original_len + 1

    # Make sure the old listener is no longer referenced
    assert old_listener not in new_node._listeners.get(event_name, [])


async def test_server_reconnect_value_updated_missing_value(
    hass: HomeAssistant,
    client,
    lock_schlage_be469,
    lock_schlage_be469_state,
    integration,
) -> None:
    """Test value_updated trigger re-registers when value is absent at reconnect."""
    trigger_type = f"{DOMAIN}.value_updated"

    no_value_filter = async_capture_events(hass, "no_value_filter")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": trigger_type,
                        "options": {
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
                        },
                    },
                    "action": {
                        "event": "no_value_filter",
                    },
                },
            ]
        },
    )

    # Remove the node so we can re-add it without the target value, simulating the
    # reconnect race where node.values is not yet fully populated when
    # _create_zwave_listeners runs.
    node_removed_event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 0,
            "node": lock_schlage_be469_state,
        },
    )
    client.driver.controller.receive_event(node_removed_event)
    assert 20 not in client.driver.controller.nodes
    await hass.async_block_till_done()

    partial_state = copy.deepcopy(lock_schlage_be469_state)
    partial_state["values"] = [
        v for v in partial_state["values"] if v.get("propertyName") != "latchStatus"
    ]
    node_added_event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": partial_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(node_added_event)
    await hass.async_block_till_done()

    # Reload the integration, which fires the connected_to_server signal that causes
    # _create_zwave_listeners to re-register listeners on the new node. With the old
    # code the missing latchStatus value would raise a KeyError and leave the trigger
    # without a listener.
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Fire a value updated event on the new node — the trigger must fire even though
    # the value was absent when _create_zwave_listeners ran.
    new_node = client.driver.controller.nodes[20]
    value_updated_event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": new_node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": CommandClass.DOOR_LOCK.value,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    new_node.receive_event(value_updated_event)
    await hass.async_block_till_done()

    assert len(no_value_filter) == 1


async def test_zwave_js_old_syntax(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test zwave_js triggers work with the old syntax."""
    node: Node = lock_schlage_be469

    zwavejs_event = async_capture_events(hass, "zwavejs_event")
    zwavejs_value_updated = async_capture_events(hass, "zwavejs_value_updated")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": f"{DOMAIN}.value_updated",
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                    },
                    "action": {
                        "event": "zwavejs_event",
                    },
                },
                {
                    "trigger": {
                        "platform": f"{DOMAIN}.event",
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "event_source": "node",
                        "event": "interview stage completed",
                    },
                    "action": {
                        "event": "zwavejs_value_updated",
                    },
                },
            ]
        },
    )

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "latchStatus",
                "newValue": "boo",
                "prevValue": "hiss",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(zwavejs_event) == 1

    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(zwavejs_value_updated) == 1


@pytest.mark.usefixtures("integration")
async def test_value_updated_command_class_options(hass: HomeAssistant) -> None:
    """Test the command class options and translations match the CommandClass enum."""
    expected = {str(cc.value) for cc in CommandClass if cc not in COMMAND_CLASS_MARKERS}

    descriptions = await trigger.async_get_all_descriptions(hass)
    options = descriptions[f"{DOMAIN}.value_updated"]["fields"]["command_class"][
        "selector"
    ]["select"]["options"]
    assert len(options) == len(expected)
    assert set(options) == expected

    translations = await async_get_translations(hass, "en", "selector", {DOMAIN})
    prefix = f"component.{DOMAIN}.selector.command_class.options."
    assert {
        key.removeprefix(prefix) for key in translations if key.startswith(prefix)
    } == expected


@pytest.mark.parametrize(
    ("trigger_type", "options_schema"),
    [
        pytest.param(f"{DOMAIN}.event", EVENT_OPTIONS_SCHEMA_DICT, id="event"),
        pytest.param(
            f"{DOMAIN}.value_updated",
            VALUE_UPDATED_OPTIONS_SCHEMA_DICT,
            id="value_updated",
        ),
    ],
)
@pytest.mark.usefixtures("integration")
async def test_trigger_description_fields_match_schema(
    hass: HomeAssistant,
    trigger_type: str,
    options_schema: dict[probatio.Marker, object],
) -> None:
    """Test the described fields match the trigger's options schema."""
    descriptions = await trigger.async_get_all_descriptions(hass)
    fields = descriptions[trigger_type]["fields"]
    assert set(fields) == {str(key) for key in options_schema}
    assert {name for name, field in fields.items() if field["required"]} == {
        str(key) for key in options_schema if isinstance(key, probatio.Required)
    }
