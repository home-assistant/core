"""Test the Z-Wave JS services."""
import pytest
import voluptuous as vol

from homeassistant.components.zwave_js.const import (
    ATTR_CONFIG_PARAMETER,
    ATTR_CONFIG_PARAMETER_BITMASK,
    ATTR_CONFIG_VALUE,
    DOMAIN,
    SERVICE_SET_CONFIG_PARAMETER,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg

from .common import AIR_TEMPERATURE_SENSOR

from tests.common import MockConfigEntry


async def test_set_config_parameter(hass, client, multisensor_6, integration):
    """Test the set_config_parameter service."""
    dev_reg = async_get_dev_reg(hass)
    ent_reg = async_get_ent_reg(hass)
    entity_entry = ent_reg.async_get(AIR_TEMPERATURE_SENSOR)

    # Test setting config parameter by property and property_key
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_PARAMETER_BITMASK: 1,
            ATTR_CONFIG_VALUE: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClassName": "Configuration",
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyName": "Group 2: Send battery reports",
        "propertyKey": 1,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "valueSize": 4,
            "min": 0,
            "max": 1,
            "default": 1,
            "format": 0,
            "allowManualEntry": True,
            "label": "Group 2: Send battery reports",
            "description": "Include battery information in periodic reports to Group 2",
            "isFromConfig": True,
        },
        "value": 0,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting parameter by property name
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: "Group 2: Send battery reports",
            ATTR_CONFIG_VALUE: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClassName": "Configuration",
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyName": "Group 2: Send battery reports",
        "propertyKey": 1,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "valueSize": 4,
            "min": 0,
            "max": 1,
            "default": 1,
            "format": 0,
            "allowManualEntry": True,
            "label": "Group 2: Send battery reports",
            "description": "Include battery information in periodic reports to Group 2",
            "isFromConfig": True,
        },
        "value": 0,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting parameter by property name and state label
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_DEVICE_ID: entity_entry.device_id,
            ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
            ATTR_CONFIG_VALUE: "Fahrenheit",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClassName": "Configuration",
        "commandClass": 112,
        "endpoint": 0,
        "property": 41,
        "propertyName": "Temperature Threshold (Unit)",
        "propertyKey": 15,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "valueSize": 3,
            "min": 1,
            "max": 2,
            "default": 1,
            "format": 0,
            "allowManualEntry": False,
            "states": {"1": "Celsius", "2": "Fahrenheit"},
            "label": "Temperature Threshold (Unit)",
            "isFromConfig": True,
        },
        "value": 0,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test setting parameter by property and bitmask
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_PARAMETER_BITMASK: "0x01",
            ATTR_CONFIG_VALUE: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClassName": "Configuration",
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyName": "Group 2: Send battery reports",
        "propertyKey": 1,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "valueSize": 4,
            "min": 0,
            "max": 1,
            "default": 1,
            "format": 0,
            "allowManualEntry": True,
            "label": "Group 2: Send battery reports",
            "description": "Include battery information in periodic reports to Group 2",
            "isFromConfig": True,
        },
        "value": 0,
    }
    assert args["value"] == 1

    # Test that an invalid entity ID raises a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: "sensor.fake_entity",
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )

    # Test that an invalid device ID raises a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_DEVICE_ID: "fake_device_id",
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )

    # Test that we can't include a bitmask value if parameter is a string
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_DEVICE_ID: entity_entry.device_id,
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_PARAMETER_BITMASK: 1,
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )

    non_zwave_js_config_entry = MockConfigEntry(entry_id="fake_entry_id")
    non_zwave_js_config_entry.add_to_hass(hass)
    non_zwave_js_device = dev_reg.async_get_or_create(
        config_entry_id=non_zwave_js_config_entry.entry_id,
        identifiers={("test", "test")},
    )

    # Test that a non Z-Wave JS device raises a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_DEVICE_ID: non_zwave_js_device.id,
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )

    zwave_js_device_with_invalid_node_id = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={(DOMAIN, "500-500")}
    )

    # Test that a Z-Wave JS device with an invalid node ID raises a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_DEVICE_ID: zwave_js_device_with_invalid_node_id.id,
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )

    non_zwave_js_entity = ent_reg.async_get_or_create(
        "test",
        "sensor",
        "test_sensor",
        suggested_object_id="test_sensor",
        config_entry=non_zwave_js_config_entry,
    )

    # Test that a non Z-Wave JS entity raises a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: non_zwave_js_entity.entity_id,
                ATTR_CONFIG_PARAMETER: "Temperature Threshold (Unit)",
                ATTR_CONFIG_VALUE: "Fahrenheit",
            },
            blocking=True,
        )
