"""The tests for Z-Wave JS device actions."""
from unittest.mock import patch

import pytest
import voluptuous_serialize
from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zwave_js import DOMAIN, device_action
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations


async def test_get_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected actions from a zwave_js node."""
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device = device_registry.async_get_device({get_device_id(driver, node)})
    assert device
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "clear_lock_usercode",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "set_lock_usercode",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "refresh_value",
            "device_id": device.id,
            "entity_id": "binary_sensor.touchscreen_deadbolt_low_battery_level",
            "metadata": {"secondary": True},
        },
        {
            "domain": DOMAIN,
            "type": "refresh_value",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "set_value",
            "device_id": device.id,
            "metadata": {},
        },
        {
            "domain": DOMAIN,
            "type": "ping",
            "device_id": device.id,
            "metadata": {},
        },
        {
            "domain": DOMAIN,
            "type": "set_config_parameter",
            "device_id": device.id,
            "parameter": 3,
            "bitmask": None,
            "subtype": "3 (Beeper)",
            "metadata": {},
        },
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    for action in expected_actions:
        assert action in actions

    # Test that we don't return actions for a controller node
    device = device_registry.async_get_device(
        {get_device_id(driver, client.driver.controller.nodes[1])}
    )
    assert device
    assert (
        await async_get_device_automations(hass, DeviceAutomationType.ACTION, device.id)
        == []
    )


async def test_get_actions_meter(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected meter actions from a zwave_js node."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device = device_registry.async_get_device({get_device_id(driver, node)})
    assert device
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    filtered_actions = [action for action in actions if action["type"] == "reset_meter"]
    assert len(filtered_actions) > 0


async def test_actions(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test actions."""
    node = climate_radio_thermostat_ct100_plus
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device({device_id})
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": "climate.z_wave_thermostat",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_ping",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "ping",
                        "device_id": device.id,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_value",
                        "device_id": device.id,
                        "command_class": 112,
                        "property": 1,
                        "value": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_config_parameter",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_config_parameter",
                        "device_id": device.id,
                        "parameter": 1,
                        "bitmask": None,
                        "subtype": "3 (Beeper)",
                        "value": 1,
                    },
                },
            ]
        },
    )

    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"

    # Call action a second time to confirm that it works (this was previously a bug)
    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"

    with patch("zwave_js_server.model.node.Node.async_ping") as mock_call:
        hass.bus.async_fire("test_event_ping")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 0

    with patch("zwave_js_server.model.node.Node.async_set_value") as mock_call:
        hass.bus.async_fire("test_event_set_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == "13-112-0-1"
        assert args[1] == 1

    with patch(
        "homeassistant.components.zwave_js.services.async_set_config_parameter"
    ) as mock_call:
        hass.bus.async_fire("test_event_set_config_parameter")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == 13
        assert args[1] == 1
        assert args[2] == 1


async def test_actions_multiple_calls(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test actions can be called multiple times and still work."""
    node = climate_radio_thermostat_ct100_plus
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device({device_id})
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": "climate.z_wave_thermostat",
                    },
                },
            ]
        },
    )

    # Trigger automation multiple times to confirm that it works each time
    for _ in range(5):
        with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
            hass.bus.async_fire("test_event_refresh_value")
            await hass.async_block_till_done()
            mock_call.assert_called_once()
            args = mock_call.call_args_list[0][0]
            assert len(args) == 1
            assert args[0].value_id == "13-64-1-mode"


async def test_lock_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test actions for locks."""
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device({device_id})
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_clear_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "clear_lock_usercode",
                        "device_id": device.id,
                        "entity_id": "lock.touchscreen_deadbolt",
                        "code_slot": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_lock_usercode",
                        "device_id": device.id,
                        "entity_id": "lock.touchscreen_deadbolt",
                        "code_slot": 1,
                        "usercode": "1234",
                    },
                },
            ]
        },
    )

    with patch("homeassistant.components.zwave_js.lock.clear_usercode") as mock_call:
        hass.bus.async_fire("test_event_clear_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0].node_id == node.node_id
        assert args[1] == 1

    with patch("homeassistant.components.zwave_js.lock.set_usercode") as mock_call:
        hass.bus.async_fire("test_event_set_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == node.node_id
        assert args[1] == 1
        assert args[2] == "1234"


async def test_reset_meter_action(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test reset_meter action."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device({device_id})
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_reset_meter",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "reset_meter",
                        "device_id": device.id,
                        "entity_id": "sensor.smart_switch_6_electric_consumed_kwh",
                    },
                },
            ]
        },
    )

    with patch(
        "zwave_js_server.model.endpoint.Endpoint.async_invoke_cc_api"
    ) as mock_call:
        hass.bus.async_fire("test_event_reset_meter")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == CommandClass.METER
        assert args[1] == "reset"


async def test_get_action_capabilities(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected action capabilities."""
    device = device_registry.async_get_device(
        {get_device_id(client.driver, climate_radio_thermostat_ct100_plus)}
    )
    assert device

    # Test refresh_value
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "refresh_value",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"type": "boolean", "name": "refresh_all_values", "optional": True}]

    # Test ping
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "ping",
        },
    )
    assert not capabilities

    # Test set_value
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_value",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    cc_options = [
        (133, "Association"),
        (89, "Association Group Information"),
        (128, "Battery"),
        (129, "Clock"),
        (112, "Configuration"),
        (90, "Device Reset Locally"),
        (122, "Firmware Update Meta Data"),
        (135, "Indicator"),
        (114, "Manufacturer Specific"),
        (96, "Multi Channel"),
        (142, "Multi Channel Association"),
        (49, "Multilevel Sensor"),
        (115, "Powerlevel"),
        (68, "Thermostat Fan Mode"),
        (69, "Thermostat Fan State"),
        (64, "Thermostat Mode"),
        (66, "Thermostat Operating State"),
        (67, "Thermostat Setpoint"),
        (134, "Version"),
        (94, "Z-Wave Plus Info"),
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
        {"type": "boolean", "name": "wait_for_result", "optional": True},
    ]

    # Test enumerated type param
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "parameter": 1,
            "bitmask": None,
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
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "parameter": 10,
            "bitmask": None,
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
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "parameter": 2,
            "bitmask": None,
            "subtype": "2 (HVAC Settings)",
        },
    )
    assert not capabilities


async def test_get_action_capabilities_lock_triggers(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected action capabilities for lock triggers."""
    device = dr.async_entries_for_config_entry(device_registry, integration.entry_id)[0]

    # Test clear_lock_usercode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
            "type": "clear_lock_usercode",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"type": "string", "name": "code_slot", "required": True}]

    # Test set_lock_usercode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
            "type": "set_lock_usercode",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {"type": "string", "name": "code_slot", "required": True},
        {"type": "string", "name": "usercode", "required": True},
    ]


async def test_get_action_capabilities_meter_triggers(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected action capabilities for meter triggers."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device = device_registry.async_get_device({get_device_id(driver, node)})
    assert device
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": "sensor.meter",
            "type": "reset_meter",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"type": "string", "name": "value", "optional": True}]


async def test_failure_scenarios(
    hass: HomeAssistant,
    client: Client,
    hank_binary_switch: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test failure scenarios."""
    device = dr.async_entries_for_config_entry(device_registry, integration.entry_id)[0]

    with pytest.raises(HomeAssistantError):
        await device_action.async_call_action_from_config(
            hass, {"type": "failed.test", "device_id": device.id}, {}, None
        )

    assert (
        await device_action.async_get_action_capabilities(
            hass, {"type": "failed.test", "device_id": device.id}
        )
        == {}
    )


async def test_unavailable_entity_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test unavailable entities are not included in actions list."""
    entity_id_unavailable = "binary_sensor.touchscreen_deadbolt_home_security_intrusion"
    hass.states.async_set(entity_id_unavailable, STATE_UNAVAILABLE, force_update=True)
    await hass.async_block_till_done()
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device = device_registry.async_get_device({get_device_id(driver, node)})
    assert device
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    assert not any(
        action.get("entity_id") == entity_id_unavailable for action in actions
    )
