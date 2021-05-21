"""Test the Z-Wave JS services."""
import pytest
import voluptuous as vol
from zwave_js_server.exceptions import SetValueFailed

from homeassistant.components.zwave_js.const import (
    ATTR_COMMAND_CLASS,
    ATTR_CONFIG_PARAMETER,
    ATTR_CONFIG_PARAMETER_BITMASK,
    ATTR_CONFIG_VALUE,
    ATTR_PROPERTY,
    ATTR_REFRESH_ALL_VALUES,
    ATTR_VALUE,
    ATTR_WAIT_FOR_RESULT,
    DOMAIN,
    SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
    SERVICE_REFRESH_VALUE,
    SERVICE_SET_CONFIG_PARAMETER,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get as async_get_dev_reg,
)
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg

from .common import (
    AIR_TEMPERATURE_SENSOR,
    CLIMATE_DANFOSS_LC13_ENTITY,
    CLIMATE_RADIO_THERMOSTAT_ENTITY,
)

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

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
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

    client.async_send_command_no_wait.reset_mock()

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

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
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

    client.async_send_command_no_wait.reset_mock()

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

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
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

    client.async_send_command_no_wait.reset_mock()

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

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
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

    # Test that when a device is awake, we call async_send_command instead of
    # async_send_command_no_wait
    multisensor_6.handle_wake_up(None)
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


async def test_bulk_set_config_parameters(hass, client, multisensor_6, integration):
    """Test the bulk_set_partial_config_parameters service."""
    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, integration.entry_id)[0]
    # Test setting config parameter by property and property_key
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_VALUE: 241,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_VALUE: {
                1: 1,
                16: 1,
                32: 1,
                64: 1,
                128: 1,
            },
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_VALUE: {
                "0x1": 1,
                "0x10": 1,
                "0x20": 1,
                "0x40": 1,
                "0x80": 1,
            },
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()

    # Test that when a device is awake, we call async_send_command instead of
    # async_send_command_no_wait
    multisensor_6.handle_wake_up(None)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_VALUE: {
                1: 1,
                16: 1,
                32: 1,
                64: 1,
                128: 1,
            },
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command.reset_mock()


async def test_poll_value(
    hass, client, climate_radio_thermostat_ct100_plus_different_endpoints, integration
):
    """Test the poll_value service."""
    # Test polling the primary value
    client.async_send_command.return_value = {"result": 2}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.poll_value"
    assert args["nodeId"] == 26
    assert args["valueId"] == {
        "commandClassName": "Thermostat Mode",
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Thermostat mode",
            "states": {
                "0": "Off",
                "1": "Heat",
                "2": "Cool",
            },
        },
        "value": 2,
        "ccVersion": 0,
    }

    client.async_send_command.reset_mock()

    # Test polling all watched values
    client.async_send_command.return_value = {"result": 2}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_REFRESH_ALL_VALUES: True,
        },
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 8

    # Test polling against an invalid entity raises ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_VALUE,
            {ATTR_ENTITY_ID: "sensor.fake_entity_id"},
            blocking=True,
        )


async def test_set_value(hass, client, climate_danfoss_lc_13, integration):
    """Test set_value service."""
    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, integration.entry_id)[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_COMMAND_CLASS: 117,
            ATTR_PROPERTY: "local",
            ATTR_VALUE: 2,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "commandClassName": "Protection",
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
        "propertyName": "local",
        "ccVersion": 2,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Local protection state",
            "states": {"0": "Unprotected", "2": "NoOperationPossible"},
        },
        "value": 0,
    }
    assert args["value"] == 2

    client.async_send_command_no_wait.reset_mock()

    # Test that when a command fails we raise an exception
    client.async_send_command.return_value = {"success": False}

    with pytest.raises(SetValueFailed):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_DEVICE_ID: device.id,
                ATTR_COMMAND_CLASS: 117,
                ATTR_PROPERTY: "local",
                ATTR_VALUE: 2,
                ATTR_WAIT_FOR_RESULT: True,
            },
            blocking=True,
        )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "commandClassName": "Protection",
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
        "propertyName": "local",
        "ccVersion": 2,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Local protection state",
            "states": {"0": "Unprotected", "2": "NoOperationPossible"},
        },
        "value": 0,
    }
    assert args["value"] == 2
