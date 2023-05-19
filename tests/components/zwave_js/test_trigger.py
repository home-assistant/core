"""The tests for Z-Wave JS automation triggers."""
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components import automation
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.components.zwave_js.trigger import async_validate_trigger_config
from homeassistant.components.zwave_js.triggers.trigger_helpers import (
    async_bypass_dynamic_config_validation,
)
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.setup import async_setup_component

from .common import SCHLAGE_BE469_LOCK_ENTITY

from tests.common import async_capture_events


async def test_zwave_js_value_updated(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test for zwave_js.value_updated automation trigger."""
    trigger_type = f"{DOMAIN}.value_updated"
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
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
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                    },
                    "action": {
                        "event": "no_value_filter",
                    },
                },
                # single from value filter
                {
                    "trigger": {
                        "platform": trigger_type,
                        "device_id": device.id,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                        "from": "ajar",
                    },
                    "action": {
                        "event": "single_from_value_filter",
                    },
                },
                # multiple from value filters
                {
                    "trigger": {
                        "platform": trigger_type,
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                        "from": ["closed", "opened"],
                    },
                    "action": {
                        "event": "multiple_from_value_filters",
                    },
                },
                # from and to value filters
                {
                    "trigger": {
                        "platform": trigger_type,
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                        "from": ["closed", "opened"],
                        "to": ["opened"],
                    },
                    "action": {
                        "event": "from_and_to_value_filters",
                    },
                },
                # different value
                {
                    "trigger": {
                        "platform": trigger_type,
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "boltStatus",
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

    with patch("homeassistant.config.load_yaml", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)


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
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
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
                            "entity_id": "sensor.test",
                            "command_class": CommandClass.DOOR_LOCK.value,
                            "property": "latchStatus",
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
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
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
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test for zwave_js.event automation trigger."""
    trigger_type = f"{DOMAIN}.event"
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
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
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "event_source": "node",
                        "event": "interview stage completed",
                    },
                    "action": {
                        "event": "node_no_event_data_filter",
                    },
                },
                # node filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "device_id": device.id,
                        "event_source": "node",
                        "event": "interview stage completed",
                        "event_data": {"stageName": "ProtocolInfo"},
                    },
                    "action": {
                        "event": "node_event_data_filter",
                    },
                },
                # controller filter: no event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "config_entry_id": integration.entry_id,
                        "event_source": "controller",
                        "event": "inclusion started",
                    },
                    "action": {
                        "event": "controller_no_event_data_filter",
                    },
                },
                # controller filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "config_entry_id": integration.entry_id,
                        "event_source": "controller",
                        "event": "inclusion started",
                        "event_data": {"secure": True},
                    },
                    "action": {
                        "event": "controller_event_data_filter",
                    },
                },
                # driver filter: no event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "config_entry_id": integration.entry_id,
                        "event_source": "driver",
                        "event": "logging",
                    },
                    "action": {
                        "event": "driver_no_event_data_filter",
                    },
                },
                # driver filter: event data
                {
                    "trigger": {
                        "platform": trigger_type,
                        "config_entry_id": integration.entry_id,
                        "event_source": "driver",
                        "event": "logging",
                        "event_data": {"message": "test"},
                    },
                    "action": {
                        "event": "driver_event_data_filter",
                    },
                },
                # node filter: event data, no partial dict match
                {
                    "trigger": {
                        "platform": trigger_type,
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "event_source": "node",
                        "event": "value updated",
                        "event_data": {"args": {"commandClassName": "Door Lock"}},
                    },
                    "action": {
                        "event": "node_event_data_no_partial_dict_match_filter",
                    },
                },
                # node filter: event data, partial dict match
                {
                    "trigger": {
                        "platform": trigger_type,
                        "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                        "event_source": "node",
                        "event": "value updated",
                        "event_data": {"args": {"commandClassName": "Door Lock"}},
                        "partial_dict_match": True,
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
            "secure": False,
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
            "secure": True,
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

    with patch("homeassistant.config.load_yaml", return_value={}):
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
                            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
                            "event_source": "node",
                            "event": "interview stage completed",
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
                            "entity_id": "sensor.fake",
                            "event_source": "node",
                            "event": "interview stage completed",
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
                        "config_entry_id": "not_real_entry_id",
                        "event_source": "controller",
                        "event": "inclusion started",
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


async def test_async_validate_trigger_config(hass: HomeAssistant) -> None:
    """Test async_validate_trigger_config."""
    mock_platform = AsyncMock()
    with patch(
        "homeassistant.components.zwave_js.trigger._get_trigger_platform",
        return_value=mock_platform,
    ):
        mock_platform.async_validate_trigger_config.return_value = {}
        await async_validate_trigger_config(hass, {})
        mock_platform.async_validate_trigger_config.assert_awaited()


async def test_invalid_trigger_configs(hass: HomeAssistant) -> None:
    """Test invalid trigger configs."""
    with pytest.raises(vol.Invalid):
        await async_validate_trigger_config(
            hass,
            {
                "platform": f"{DOMAIN}.event",
                "entity_id": "fake.entity",
                "event_source": "node",
                "event": "value updated",
            },
        )

    with pytest.raises(vol.Invalid):
        await async_validate_trigger_config(
            hass,
            {
                "platform": f"{DOMAIN}.value_updated",
                "entity_id": "fake.entity",
                "command_class": CommandClass.DOOR_LOCK.value,
                "property": "latchStatus",
            },
        )


async def test_zwave_js_trigger_config_entry_unloaded(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test zwave_js triggers bypass dynamic validation when needed."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    # Test bypass check is False
    assert not async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.value_updated",
            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
        },
    )

    await hass.config_entries.async_unload(integration.entry_id)

    # Test full validation for both events
    assert await async_validate_trigger_config(
        hass,
        {
            "platform": f"{DOMAIN}.value_updated",
            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
        },
    )

    assert await async_validate_trigger_config(
        hass,
        {
            "platform": f"{DOMAIN}.event",
            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
            "event_source": "node",
            "event": "interview stage completed",
        },
    )

    # Test bypass check
    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.value_updated",
            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.value_updated",
            "device_id": device.id,
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
            "from": "ajar",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.event",
            "entity_id": SCHLAGE_BE469_LOCK_ENTITY,
            "event_source": "node",
            "event": "interview stage completed",
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.event",
            "device_id": device.id,
            "event_source": "node",
            "event": "interview stage completed",
            "event_data": {"stageName": "ProtocolInfo"},
        },
    )

    assert async_bypass_dynamic_config_validation(
        hass,
        {
            "platform": f"{DOMAIN}.event",
            "config_entry_id": integration.entry_id,
            "event_source": "controller",
            "event": "nvm convert progress",
        },
    )
