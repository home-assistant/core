"""The tests for Z-Wave JS device conditions."""
from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol
import voluptuous_serialize
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.zwave_js import DOMAIN, device_condition
from homeassistant.components.zwave_js.helpers import (
    get_device_id,
    get_zwave_value_from_config,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_conditions(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected onditions from a zwave_js."""
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device
    config_value = list(lock_schlage_be469.get_configuration_values().values())[0]
    value_id = config_value.value_id
    name = config_value.property_name

    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "node_status",
            "device_id": device.id,
            "metadata": {},
        },
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "config_parameter",
            "device_id": device.id,
            "value_id": value_id,
            "subtype": f"{config_value.property_} ({name})",
            "metadata": {},
        },
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "value",
            "device_id": device.id,
            "metadata": {},
        },
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device.id
    )
    for condition in expected_conditions:
        assert condition in conditions

    # Test that we don't return actions for a controller node
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, client.driver.controller.nodes[1])}
    )
    assert device
    assert (
        await async_get_device_automations(
            hass, DeviceAutomationType.CONDITION, device.id
        )
        == []
    )


async def test_node_status_state(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for node_status conditions."""
    dev_reg = device_registry.async_get(hass)
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
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "node_status",
                            "status": "alive",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "alive - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "node_status",
                            "status": "awake",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "awake - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "node_status",
                            "status": "asleep",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "asleep - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event4"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "node_status",
                            "status": "dead",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "dead - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "alive - event - test_event1"

    event = Event(
        "wake up",
        data={
            "source": "node",
            "event": "wake up",
            "nodeId": lock_schlage_be469.node_id,
        },
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "awake - event - test_event2"

    event = Event(
        "sleep",
        data={"source": "node", "event": "sleep", "nodeId": lock_schlage_be469.node_id},
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "asleep - event - test_event3"

    event = Event(
        "dead",
        data={"source": "node", "event": "dead", "nodeId": lock_schlage_be469.node_id},
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data["some"] == "dead - event - test_event4"


async def test_config_parameter_state(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for config_parameter conditions."""
    dev_reg = device_registry.async_get(hass)
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
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "config_parameter",
                            "value_id": f"{lock_schlage_be469.node_id}-112-0-3",
                            "subtype": "3 (Beeper)",
                            "value": 255,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "Beeper - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "config_parameter",
                            "value_id": f"{lock_schlage_be469.node_id}-112-0-6",
                            "subtype": "6 (User Slot Status)",
                            "value": 1,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "User Slot Status - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "Beeper - event - test_event1"

    # Flip Beeper state to not match condition
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": lock_schlage_be469.node_id,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 3,
                "newValue": 0,
                "prevValue": 255,
            },
        },
    )
    lock_schlage_be469.receive_event(event)

    # Flip User Slot Status to match condition
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": lock_schlage_be469.node_id,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 6,
                "newValue": 1,
                "prevValue": 117440512,
            },
        },
    )
    lock_schlage_be469.receive_event(event)

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "User Slot Status - event - test_event2"


async def test_value_state(
    hass: HomeAssistant, client, lock_schlage_be469, integration, calls
) -> None:
    """Test for value conditions."""
    dev_reg = device_registry.async_get(hass)
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
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "value",
                            "command_class": 112,
                            "property": 3,
                            "value": 255,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "value - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "value - event - test_event1"


async def test_get_condition_capabilities_node_status(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we don't get capabilities from a node_status condition."""
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "node_status",
        },
    )
    assert capabilities and "extra_fields" in capabilities
    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "status",
            "required": True,
            "type": "select",
            "options": [
                ("asleep", "asleep"),
                ("awake", "awake"),
                ("dead", "dead"),
                ("alive", "alive"),
            ],
        }
    ]


async def test_get_condition_capabilities_value(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test we get the expected capabilities from a value condition."""
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "value",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    cc_options = [
        (133, "Association"),
        (128, "Battery"),
        (98, "Door Lock"),
        (122, "Firmware Update Meta Data"),
        (114, "Manufacturer Specific"),
        (113, "Notification"),
        (152, "Security"),
        (99, "User Code"),
        (134, "Version"),
    ]

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "command_class",
            "required": True,
            "options": cc_options,
            "type": "select",
        },
        {"name": "property", "required": True, "type": "string"},
        {"name": "property_key", "optional": True, "type": "string"},
        {"name": "endpoint", "optional": True, "type": "string"},
        {"name": "value", "required": True, "type": "string"},
    ]


async def test_get_condition_capabilities_config_parameter(
    hass: HomeAssistant, client, climate_radio_thermostat_ct100_plus, integration
) -> None:
    """Test we get the expected capabilities from a config_parameter condition."""
    node = climate_radio_thermostat_ct100_plus
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, climate_radio_thermostat_ct100_plus)}
    )
    assert device

    # Test enumerated type param
    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "config_parameter",
            "value_id": f"{node.node_id}-112-0-1",
            "subtype": "1 (Temperature Reporting Threshold)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "required": True,
            "options": [
                (0, "Disabled"),
                (1, "0.5° F"),
                (2, "1.0° F"),
                (3, "1.5° F"),
                (4, "2.0° F"),
            ],
            "type": "select",
        }
    ]

    # Test range type param
    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "config_parameter",
            "value_id": f"{node.node_id}-112-0-10",
            "subtype": "10 (Temperature Reporting Filter)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "required": True,
            "type": "integer",
            "valueMin": 0,
            "valueMax": 124,
        }
    ]

    # Test undefined type param
    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "config_parameter",
            "value_id": f"{node.node_id}-112-0-2",
            "subtype": "2 (HVAC Settings)",
        },
    )
    assert not capabilities


async def test_failure_scenarios(
    hass: HomeAssistant, client, hank_binary_switch, integration
) -> None:
    """Test failure scenarios."""
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device(
        {get_device_id(client.driver, hank_binary_switch)}
    )
    assert device

    with pytest.raises(HomeAssistantError):
        await device_condition.async_condition_from_config(
            hass, {"type": "failed.test", "device_id": device.id}
        )

    with patch(
        "homeassistant.components.zwave_js.device_condition.async_get_node_from_device_id",
        return_value=None,
    ), patch(
        "homeassistant.components.zwave_js.device_condition.get_zwave_value_from_config",
        return_value=None,
    ):
        assert (
            await device_condition.async_get_condition_capabilities(
                hass, {"type": "failed.test", "device_id": device.id}
            )
            == {}
        )

    INVALID_CONFIG = {
        "condition": "device",
        "domain": DOMAIN,
        "device_id": device.id,
        "type": "value",
        "command_class": CommandClass.DOOR_LOCK.value,
        "property": 9999,
        "property_key": 9999,
        "endpoint": 9999,
        "value": 9999,
    }

    # Test that invalid config raises exception
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_condition.async_validate_condition_config(hass, INVALID_CONFIG)

    # Unload entry so we can verify that validation will pass on an invalid config
    # since we return early
    await hass.config_entries.async_unload(integration.entry_id)
    assert (
        await device_condition.async_validate_condition_config(hass, INVALID_CONFIG)
        == INVALID_CONFIG
    )

    # Test invalid device ID fails validation
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_condition.async_validate_condition_config(
            hass,
            {
                "condition": "device",
                "domain": DOMAIN,
                "type": "value",
                "device_id": "invalid_device_id",
                "command_class": CommandClass.DOOR_LOCK.value,
                "property": 9999,
                "property_key": 9999,
                "endpoint": 9999,
                "value": 9999,
            },
        )


async def test_get_value_from_config_failure(
    hass: HomeAssistant, client, hank_binary_switch, integration
) -> None:
    """Test get_value_from_config invalid value ID."""
    with pytest.raises(vol.Invalid):
        get_zwave_value_from_config(
            hank_binary_switch,
            {
                "command_class": CommandClass.SCENE_ACTIVATION.value,
                "property": "sceneId",
                "property_key": 15,
                "endpoint": 10,
            },
        )
