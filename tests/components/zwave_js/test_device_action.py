"""The tests for Z-Wave JS device actions."""
import pytest
import voluptuous_serialize
from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node

from homeassistant.components import automation
from homeassistant.components.zwave_js import DOMAIN, device_action
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service


async def test_get_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
) -> None:
    """Test we get the expected actions from a zwave_js node."""
    node = lock_schlage_be469
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device({get_device_id(client, node)})
    assert device
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "clear_lock_usercode",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
        },
        {
            "domain": DOMAIN,
            "type": "set_lock_usercode",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
        },
        {
            "domain": DOMAIN,
            "type": "refresh_value",
            "device_id": device.id,
            "entity_id": "lock.touchscreen_deadbolt",
        },
        {
            "domain": DOMAIN,
            "type": "set_value",
            "device_id": device.id,
        },
        {
            "domain": DOMAIN,
            "type": "ping",
            "device_id": device.id,
        },
        {
            "domain": DOMAIN,
            "type": "set_config_parameter",
            "device_id": device.id,
            "parameter": 3,
            "bitmask": None,
            "subtype": f"{node.node_id}-112-0-3 (Beeper)",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device.id)
    for action in expected_actions:
        assert action in actions


async def test_get_actions_meter(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
) -> None:
    """Test we get the expected meter actions from a zwave_js node."""
    node = aeon_smart_switch_6
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device({get_device_id(client, node)})
    assert device
    actions = await async_get_device_automations(hass, "action", device.id)
    filtered_actions = [action for action in actions if action["type"] == "reset_meter"]
    assert len(filtered_actions) > 0


async def test_action(hass: HomeAssistant) -> None:
    """Test for turn_on and turn_off actions."""
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
                        "device_id": "fake",
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
                        "device_id": "fake",
                        "entity_id": "lock.touchscreen_deadbolt",
                        "code_slot": 1,
                        "usercode": "1234",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": "fake",
                        "entity_id": "lock.touchscreen_deadbolt",
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
                        "device_id": "fake",
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
                        "device_id": "fake",
                        "command_class": 112,
                        "property": "test",
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
                        "device_id": "fake",
                        "parameter": 3,
                        "bitmask": None,
                        "subtype": "2-112-0-3 (Beeper)",
                        "value": 255,
                    },
                },
            ]
        },
    )

    clear_lock_usercode = async_mock_service(hass, "zwave_js", "clear_lock_usercode")
    hass.bus.async_fire("test_event_clear_lock_usercode")
    await hass.async_block_till_done()
    assert len(clear_lock_usercode) == 1

    set_lock_usercode = async_mock_service(hass, "zwave_js", "set_lock_usercode")
    hass.bus.async_fire("test_event_set_lock_usercode")
    await hass.async_block_till_done()
    assert len(set_lock_usercode) == 1

    refresh_value = async_mock_service(hass, "zwave_js", "refresh_value")
    hass.bus.async_fire("test_event_refresh_value")
    await hass.async_block_till_done()
    assert len(refresh_value) == 1

    ping = async_mock_service(hass, "zwave_js", "ping")
    hass.bus.async_fire("test_event_ping")
    await hass.async_block_till_done()
    assert len(ping) == 1

    set_value = async_mock_service(hass, "zwave_js", "set_value")
    hass.bus.async_fire("test_event_set_value")
    await hass.async_block_till_done()
    assert len(set_value) == 1

    set_config_parameter = async_mock_service(hass, "zwave_js", "set_config_parameter")
    hass.bus.async_fire("test_event_set_config_parameter")
    await hass.async_block_till_done()
    assert len(set_config_parameter) == 1


async def test_get_action_capabilities(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
):
    """Test we get the expected action capabilities."""
    node = climate_radio_thermostat_ct100_plus
    dev_reg = device_registry.async_get(hass)
    device = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )[0]

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

    cc_options = [(cc.value, cc.name) for cc in CommandClass]

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
            "subtype": f"{node.node_id}-112-0-1 (Temperature Reporting Threshold)",
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
            "subtype": f"{node.node_id}-112-0-10 (Temperature Reporting Filter)",
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
            "subtype": f"{node.node_id}-112-0-2 (HVAC Settings)",
        },
    )
    assert not capabilities


async def test_get_action_capabilities_lock_triggers(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
):
    """Test we get the expected action capabilities for lock triggers."""
    dev_reg = device_registry.async_get(hass)
    device = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )[0]

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
) -> None:
    """Test we get the expected action capabilities for meter triggers."""
    node = aeon_smart_switch_6
    dev_reg = device_registry.async_get(hass)
    device = dev_reg.async_get_device({get_device_id(client, node)})
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
):
    """Test failure scenarios."""
    dev_reg = device_registry.async_get(hass)
    device = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )[0]

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
