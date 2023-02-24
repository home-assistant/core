"""The tests for Z-Wave JS device triggers."""
from unittest.mock import patch

import pytest
import voluptuous_serialize
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.zwave_js import DOMAIN, device_trigger
from homeassistant.components.zwave_js.helpers import (
    async_get_node_status_sensor_entity_id,
    get_device_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_no_controller_triggers(hass: HomeAssistant, client, integration) -> None:
    """Test that we do not get triggers for the controller."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, client.driver.controller.nodes[1])}
    )
    assert device
    assert (
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        == []
    )


async def test_get_notification_notification_triggers(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected triggers from a zwave_js device with the Notification CC."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "event.notification.notification",
        "device_id": device.id,
        "command_class": CommandClass.NOTIFICATION,
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_notification_notification_fires(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for event.notification.notification trigger firing."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # event, type, label
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.notification.notification",
                        "command_class": CommandClass.NOTIFICATION.value,
                        "type.": 6,
                        "event": 5,
                        "label": "Access Control",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.notification.notification - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
                # no type, event, label
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.notification.notification",
                        "command_class": CommandClass.NOTIFICATION.value,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.notification.notification2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake Notification CC notification
    event = Event(
        type="notification",
        data={
            "source": "node",
            "event": "notification",
            "nodeId": node.node_id,
            "ccId": 113,
            "args": {
                "type": 6,
                "event": 5,
                "label": "Access Control",
                "eventLabel": "Keypad lock operation",
                "parameters": {"userId": 1},
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data[
        "some"
    ] == "event.notification.notification - device - zwave_js_notification - {}".format(
        CommandClass.NOTIFICATION
    )
    assert calls[1].data[
        "some"
    ] == "event.notification.notification2 - device - zwave_js_notification - {}".format(
        CommandClass.NOTIFICATION
    )


async def test_get_trigger_capabilities_notification_notification(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a notification.notification trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "event.notification.notification",
            "command_class": CommandClass.NOTIFICATION.value,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert_lists_same(
        voluptuous_serialize.convert(
            capabilities["extra_fields"], custom_serializer=cv.custom_serializer
        ),
        [
            {"name": "type.", "optional": True, "type": "string"},
            {"name": "label", "optional": True, "type": "string"},
            {"name": "event", "optional": True, "type": "string"},
            {"name": "event_label", "optional": True, "type": "string"},
        ],
    )


async def test_if_entry_control_notification_fires(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for notification.entry_control trigger firing."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # event_type and data_type
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.notification.entry_control",
                        "command_class": CommandClass.ENTRY_CONTROL.value,
                        "event_type": 5,
                        "data_type": 2,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.notification.notification - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
                # no event_type and data_type
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.notification.entry_control",
                        "command_class": CommandClass.ENTRY_CONTROL.value,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.notification.notification2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake Entry Control CC notification
    event = Event(
        type="notification",
        data={
            "source": "node",
            "event": "notification",
            "nodeId": node.node_id,
            "ccId": 111,
            "args": {
                "eventType": 5,
                "eventTypeLabel": "label 1",
                "dataType": 2,
                "dataTypeLabel": "label 2",
                "eventData": "555",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data[
        "some"
    ] == "event.notification.notification - device - zwave_js_notification - {}".format(
        CommandClass.ENTRY_CONTROL
    )
    assert calls[1].data[
        "some"
    ] == "event.notification.notification2 - device - zwave_js_notification - {}".format(
        CommandClass.ENTRY_CONTROL
    )


async def test_get_trigger_capabilities_entry_control_notification(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a notification.entry_control trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "event.notification.entry_control",
            "command_class": CommandClass.ENTRY_CONTROL.value,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert_lists_same(
        voluptuous_serialize.convert(
            capabilities["extra_fields"], custom_serializer=cv.custom_serializer
        ),
        [
            {"name": "event_type", "optional": True, "type": "string"},
            {"name": "data_type", "optional": True, "type": "string"},
        ],
    )


async def test_get_node_status_triggers(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected triggers from a device with node status sensor enabled."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    ent_reg = async_get_ent_reg(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device.id, ent_reg, dev_reg
    )
    ent_reg.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "state.node_status",
        "device_id": device.id,
        "entity_id": entity_id,
        "metadata": {"secondary": True},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_node_status_change_fires(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for node_status trigger firing."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    ent_reg = async_get_ent_reg(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device.id, ent_reg, dev_reg
    )
    ent_reg.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # from
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "entity_id": entity_id,
                        "type": "state.node_status",
                        "from": "alive",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "state.node_status - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.from_state.state }}"
                            )
                        },
                    },
                },
                # no from or to
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "entity_id": entity_id,
                        "type": "state.node_status",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "state.node_status2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.from_state.state }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Test status change
    event = Event(
        "dead", data={"source": "node", "event": "dead", "nodeId": node.node_id}
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data["some"] == "state.node_status - device - alive"
    assert calls[1].data["some"] == "state.node_status2 - device - alive"


async def test_get_trigger_capabilities_node_status(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a node_status trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    ent_reg = async_get_ent_reg(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device.id, ent_reg, dev_reg
    )
    ent_reg.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": entity_id,
            "type": "state.node_status",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "from",
            "optional": True,
            "options": [
                ("asleep", "asleep"),
                ("awake", "awake"),
                ("dead", "dead"),
                ("alive", "alive"),
            ],
            "type": "select",
        },
        {
            "name": "to",
            "optional": True,
            "options": [
                ("asleep", "asleep"),
                ("awake", "awake"),
                ("dead", "dead"),
                ("alive", "alive"),
            ],
            "type": "select",
        },
        {"name": "for", "optional": True, "type": "positive_time_period_dict"},
    ]


async def test_get_basic_value_notification_triggers(
    hass: HomeAssistant, client, ge_in_wall_dimmer_switch, integration
) -> None:
    """Test we get the expected triggers from a zwave_js device with the Basic CC."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, ge_in_wall_dimmer_switch)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "event.value_notification.basic",
        "device_id": device.id,
        "command_class": CommandClass.BASIC,
        "property": "event",
        "property_key": None,
        "endpoint": 0,
        "subtype": "Endpoint 0",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_basic_value_notification_fires(
    hass: HomeAssistant, client, ge_in_wall_dimmer_switch, integration, calls
) -> None:
    """Test for event.value_notification.basic trigger firing."""
    node: Node = ge_in_wall_dimmer_switch
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, ge_in_wall_dimmer_switch)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "type": "event.value_notification.basic",
                        "device_id": device.id,
                        "command_class": CommandClass.BASIC.value,
                        "property": "event",
                        "property_key": None,
                        "endpoint": 0,
                        "subtype": "Endpoint 0",
                        "value": 0,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.basic - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
                # no value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "type": "event.value_notification.basic",
                        "device_id": device.id,
                        "command_class": CommandClass.BASIC.value,
                        "property": "event",
                        "property_key": None,
                        "endpoint": 0,
                        "subtype": "Endpoint 0",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.basic2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake Basic CC value notification
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
                "value": 0,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Event value",
                    "min": 0,
                    "max": 255,
                },
                "ccVersion": 1,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data[
        "some"
    ] == "event.value_notification.basic - device - zwave_js_value_notification - {}".format(
        CommandClass.BASIC
    )
    assert calls[1].data[
        "some"
    ] == "event.value_notification.basic2 - device - zwave_js_value_notification - {}".format(
        CommandClass.BASIC
    )


async def test_get_trigger_capabilities_basic_value_notification(
    hass: HomeAssistant, client, ge_in_wall_dimmer_switch, integration
) -> None:
    """Test we get the expected capabilities from a value_notification.basic trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, ge_in_wall_dimmer_switch)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "event.value_notification.basic",
            "device_id": device.id,
            "command_class": CommandClass.BASIC.value,
            "property": "event",
            "property_key": None,
            "endpoint": 0,
            "subtype": "Endpoint 0",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "optional": True,
            "type": "integer",
            "valueMin": 0,
            "valueMax": 255,
        }
    ]


async def test_get_central_scene_value_notification_triggers(
    hass: HomeAssistant, client, wallmote_central_scene, integration
) -> None:
    """Test we get the expected triggers from a zwave_js device with the Central Scene CC."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, wallmote_central_scene)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "event.value_notification.central_scene",
        "device_id": device.id,
        "command_class": CommandClass.CENTRAL_SCENE,
        "property": "scene",
        "property_key": "001",
        "endpoint": 0,
        "subtype": "Endpoint 0 Scene 001",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_central_scene_value_notification_fires(
    hass: HomeAssistant, client, wallmote_central_scene, integration, calls
) -> None:
    """Test for event.value_notification.central_scene trigger firing."""
    node: Node = wallmote_central_scene
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, wallmote_central_scene)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.value_notification.central_scene",
                        "command_class": CommandClass.CENTRAL_SCENE.value,
                        "property": "scene",
                        "property_key": "001",
                        "endpoint": 0,
                        "subtype": "Endpoint 0 Scene 001",
                        "value": 0,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.central_scene - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
                # no value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.value_notification.central_scene",
                        "command_class": CommandClass.CENTRAL_SCENE.value,
                        "property": "scene",
                        "property_key": "001",
                        "endpoint": 0,
                        "subtype": "Endpoint 0 Scene 001",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.central_scene2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake Central Scene CC value notification
    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Central Scene",
                "commandClass": 91,
                "endpoint": 0,
                "property": "scene",
                "propertyName": "scene",
                "propertyKey": "001",
                "value": 0,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "min": 0,
                    "max": 255,
                    "label": "Scene 004",
                    "states": {
                        "0": "KeyPressed",
                        "1": "KeyReleased",
                        "2": "KeyHeldDown",
                    },
                },
                "ccVersion": 1,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data[
        "some"
    ] == "event.value_notification.central_scene - device - zwave_js_value_notification - {}".format(
        CommandClass.CENTRAL_SCENE
    )
    assert calls[1].data[
        "some"
    ] == "event.value_notification.central_scene2 - device - zwave_js_value_notification - {}".format(
        CommandClass.CENTRAL_SCENE
    )


async def test_get_trigger_capabilities_central_scene_value_notification(
    hass: HomeAssistant, client, wallmote_central_scene, integration
) -> None:
    """Test we get the expected capabilities from a value_notification.central_scene trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, wallmote_central_scene)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "event.value_notification.central_scene",
            "device_id": device.id,
            "command_class": CommandClass.CENTRAL_SCENE.value,
            "property": "scene",
            "property_key": "001",
            "endpoint": 0,
            "subtype": "Endpoint 0 Scene 001",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "optional": True,
            "type": "select",
            "options": [(0, "KeyPressed"), (1, "KeyReleased"), (2, "KeyHeldDown")],
        },
    ]


async def test_get_scene_activation_value_notification_triggers(
    hass: HomeAssistant, client, hank_binary_switch, integration
) -> None:
    """Test we get the expected triggers from a zwave_js device with the SceneActivation CC."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, hank_binary_switch)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "event.value_notification.scene_activation",
        "device_id": device.id,
        "command_class": CommandClass.SCENE_ACTIVATION.value,
        "property": "sceneId",
        "property_key": None,
        "endpoint": 0,
        "subtype": "Endpoint 0",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_scene_activation_value_notification_fires(
    hass: HomeAssistant, client, hank_binary_switch, integration, calls
) -> None:
    """Test for event.value_notification.scene_activation trigger firing."""
    node: Node = hank_binary_switch
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, hank_binary_switch)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.value_notification.scene_activation",
                        "command_class": CommandClass.SCENE_ACTIVATION.value,
                        "property": "sceneId",
                        "property_key": None,
                        "endpoint": 0,
                        "subtype": "Endpoint 0",
                        "value": 1,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.scene_activation - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
                # No value
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "event.value_notification.scene_activation",
                        "command_class": CommandClass.SCENE_ACTIVATION.value,
                        "property": "sceneId",
                        "property_key": None,
                        "endpoint": 0,
                        "subtype": "Endpoint 0",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event.value_notification.scene_activation2 - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - "
                                "{{ trigger.event.data.command_class }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake Scene Activation CC value notification
    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Scene Activation",
                "commandClass": 43,
                "endpoint": 0,
                "property": "sceneId",
                "propertyName": "sceneId",
                "value": 1,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": True,
                    "min": 1,
                    "max": 255,
                    "label": "Scene ID",
                },
                "ccVersion": 1,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data[
        "some"
    ] == "event.value_notification.scene_activation - device - zwave_js_value_notification - {}".format(
        CommandClass.SCENE_ACTIVATION
    )
    assert calls[1].data[
        "some"
    ] == "event.value_notification.scene_activation2 - device - zwave_js_value_notification - {}".format(
        CommandClass.SCENE_ACTIVATION
    )


async def test_get_trigger_capabilities_scene_activation_value_notification(
    hass: HomeAssistant, client, hank_binary_switch, integration
) -> None:
    """Test we get the expected capabilities from a value_notification.scene_activation trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, hank_binary_switch)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "event.value_notification.scene_activation",
            "device_id": device.id,
            "command_class": CommandClass.SCENE_ACTIVATION.value,
            "property": "sceneId",
            "property_key": None,
            "endpoint": 0,
            "subtype": "Endpoint 0",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "optional": True,
            "type": "integer",
            "valueMin": 1,
            "valueMax": 255,
        }
    ]


async def test_get_value_updated_value_triggers(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the zwave_js.value_updated.value trigger from a zwave_js device."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "zwave_js.value_updated.value",
        "device_id": device.id,
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_value_updated_value_fires(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for zwave_js.value_updated.value trigger firing."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "zwave_js.value_updated.value",
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                        "property_key": None,
                        "endpoint": None,
                        "from": "open",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "zwave_js.value_updated.value - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.previous_value }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake value update that shouldn't trigger
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
                "property": "insideHandlesCanOpenDoor",
                "newValue": [True, False, False, False],
                "prevValue": [False, False, False, False],
                "propertyName": "insideHandlesCanOpenDoor",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Publish fake value update that should trigger
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
                "newValue": "closed",
                "prevValue": "open",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == "zwave_js.value_updated.value - zwave_js.value_updated - open"
    )


async def test_value_updated_value_no_driver(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test zwave_js.value_updated.value trigger with missing driver."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    driver = client.driver
    client.driver = None

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "zwave_js.value_updated.value",
                        "command_class": CommandClass.DOOR_LOCK.value,
                        "property": "latchStatus",
                        "property_key": None,
                        "endpoint": None,
                        "from": "open",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "zwave_js.value_updated.value - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.previous_value }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    client.driver = driver

    # No trigger as automation failed to setup.
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
                "newValue": "closed",
                "prevValue": "open",
                "propertyName": "latchStatus",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_get_trigger_capabilities_value_updated_value(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a zwave_js.value_updated.value trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "zwave_js.value_updated.value",
            "command_class": CommandClass.DOOR_LOCK.value,
            "property": "latchStatus",
            "property_key": None,
            "endpoint": None,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "command_class",
            "required": True,
            "type": "select",
            "options": [
                (133, "Association"),
                (128, "Battery"),
                (98, "Door Lock"),
                (122, "Firmware Update Meta Data"),
                (114, "Manufacturer Specific"),
                (113, "Notification"),
                (152, "Security"),
                (99, "User Code"),
                (134, "Version"),
            ],
        },
        {"name": "property", "required": True, "type": "string"},
        {"name": "property_key", "optional": True, "type": "string"},
        {"name": "endpoint", "optional": True, "type": "string"},
        {"name": "from", "optional": True, "type": "string"},
        {"name": "to", "optional": True, "type": "string"},
    ]


async def test_get_value_updated_config_parameter_triggers(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the zwave_js.value_updated.config_parameter trigger from a zwave_js device."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "zwave_js.value_updated.config_parameter",
        "device_id": device.id,
        "property": 3,
        "property_key": None,
        "endpoint": 0,
        "command_class": CommandClass.CONFIGURATION.value,
        "subtype": "3 (Beeper)",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_value_updated_config_parameter_fires(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for zwave_js.value_updated.config_parameter trigger firing."""
    node: Node = lock_schlage_be469
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "zwave_js.value_updated.config_parameter",
                        "property": 3,
                        "property_key": None,
                        "endpoint": 0,
                        "command_class": CommandClass.CONFIGURATION.value,
                        "subtype": "3 (Beeper)",
                        "from": 255,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "zwave_js.value_updated.config_parameter - "
                                "{{ trigger.platform}} - "
                                "{{ trigger.previous_value_raw }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Publish fake value update
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 3,
                "newValue": 0,
                "prevValue": 255,
                "propertyName": "Beeper",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == "zwave_js.value_updated.config_parameter - zwave_js.value_updated - 255"
    )


async def test_get_trigger_capabilities_value_updated_config_parameter_range(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a range zwave_js.value_updated.config_parameter trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "zwave_js.value_updated.config_parameter",
            "property": 6,
            "property_key": None,
            "endpoint": 0,
            "command_class": CommandClass.CONFIGURATION.value,
            "subtype": "6 (User Slot Status)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "from",
            "optional": True,
            "valueMin": 0,
            "valueMax": 255,
            "type": "integer",
        },
        {
            "name": "to",
            "optional": True,
            "valueMin": 0,
            "valueMax": 255,
            "type": "integer",
        },
    ]


async def test_get_trigger_capabilities_value_updated_config_parameter_enumerated(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from an enumerated zwave_js.value_updated.config_parameter trigger."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "zwave_js.value_updated.config_parameter",
            "property": 3,
            "property_key": None,
            "endpoint": 0,
            "command_class": CommandClass.CONFIGURATION.value,
            "subtype": "3 (Beeper)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "from",
            "optional": True,
            "options": [(0, "Disable Beeper"), (255, "Enable Beeper")],
            "type": "select",
        },
        {
            "name": "to",
            "optional": True,
            "options": [(0, "Disable Beeper"), (255, "Enable Beeper")],
            "type": "select",
        },
    ]


async def test_failure_scenarios(
    hass: HomeAssistant, client, hank_binary_switch, integration
) -> None:
    """Test failure scenarios."""
    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass, {"type": "failed.test", "device_id": "invalid_device_id"}, None, {}
        )

    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass,
            {"type": "event.failed_type", "device_id": "invalid_device_id"},
            None,
            {},
        )

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, hank_binary_switch)}
    )
    assert device

    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass, {"type": "failed.test", "device_id": device.id}, None, {}
        )

    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass,
            {"type": "event.failed_type", "device_id": device.id},
            None,
            {},
        )

    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass,
            {"type": "state.failed_type", "device_id": device.id},
            None,
            {},
        )

    with patch(
        "homeassistant.components.zwave_js.device_trigger.async_get_node_from_device_id",
        return_value=None,
    ), patch(
        "homeassistant.components.zwave_js.helpers.get_zwave_value_from_config",
        return_value=None,
    ):
        assert (
            await device_trigger.async_get_trigger_capabilities(
                hass, {"type": "failed.test", "device_id": "invalid_device_id"}
            )
            == {}
        )

    with pytest.raises(HomeAssistantError):
        async_get_node_status_sensor_entity_id(hass, "invalid_device_id")

    INVALID_CONFIG = {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device.id,
        "type": "zwave_js.value_updated.value",
        "command_class": CommandClass.DOOR_LOCK.value,
        "property": 9999,
        "property_key": 9999,
        "endpoint": 9999,
    }

    # Test that invalid config raises exception
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, INVALID_CONFIG)

    # Unload entry so we can verify that validation will pass on an invalid config
    # since we return early
    await hass.config_entries.async_unload(integration.entry_id)
    assert (
        await device_trigger.async_validate_trigger_config(hass, INVALID_CONFIG)
        == INVALID_CONFIG
    )

    # Test invalid device ID fails validation
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(
            hass,
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": "invalid_device_id",
                "type": "zwave_js.value_updated.value",
                "command_class": CommandClass.DOOR_LOCK.value,
                "property": 9999,
                "property_key": 9999,
                "endpoint": 9999,
            },
        )
