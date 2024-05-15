"""Test the Z-Wave JS services."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.value import SetConfigParameterResult

from homeassistant.components.group import Group
from homeassistant.components.zwave_js.const import (
    ATTR_BROADCAST,
    ATTR_COMMAND_CLASS,
    ATTR_CONFIG_PARAMETER,
    ATTR_CONFIG_PARAMETER_BITMASK,
    ATTR_CONFIG_VALUE,
    ATTR_ENDPOINT,
    ATTR_METHOD_NAME,
    ATTR_NOTIFICATION_EVENT,
    ATTR_NOTIFICATION_TYPE,
    ATTR_OPTIONS,
    ATTR_PARAMETERS,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_REFRESH_ALL_VALUES,
    ATTR_VALUE,
    ATTR_VALUE_FORMAT,
    ATTR_VALUE_SIZE,
    ATTR_WAIT_FOR_RESULT,
    DOMAIN,
    SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
    SERVICE_INVOKE_CC_API,
    SERVICE_MULTICAST_SET_VALUE,
    SERVICE_PING,
    SERVICE_REFRESH_NOTIFICATIONS,
    SERVICE_REFRESH_VALUE,
    SERVICE_SET_CONFIG_PARAMETER,
    SERVICE_SET_VALUE,
)
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.area_registry import async_get as async_get_area_reg
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg
from homeassistant.setup import async_setup_component

from .common import (
    AEON_SMART_SWITCH_LIGHT_ENTITY,
    AIR_TEMPERATURE_SENSOR,
    BULB_6_MULTI_COLOR_LIGHT_ENTITY,
    CLIMATE_DANFOSS_LC13_ENTITY,
    CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
    CLIMATE_RADIO_THERMOSTAT_ENTITY,
    SCHLAGE_BE469_LOCK_ENTITY,
)

from tests.common import MockConfigEntry


async def test_set_config_parameter(
    hass: HomeAssistant,
    client,
    multisensor_6,
    aeotec_zw164_siren,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    # Test setting config parameter value in hex
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_PARAMETER_BITMASK: 1,
            ATTR_CONFIG_VALUE: "0x1",
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 41,
        "propertyKey": 15,
    }
    assert args["value"] == 2

    client.async_send_command_no_wait.reset_mock()

    # Test using area ID
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    ent_reg.async_update_entity(entity_entry.entity_id, area_id=area.id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_AREA_ID: area.id,
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 41,
        "propertyKey": 15,
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    # Test setting parameter by value_size
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 2,
            ATTR_VALUE_SIZE: 2,
            ATTR_VALUE_FORMAT: 1,
            ATTR_CONFIG_VALUE: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.set_raw_config_parameter_value"
    assert args["nodeId"] == 52
    assert args["endpoint"] == 0
    options = args["options"]
    assert options["parameter"] == 2
    assert options["value"] == 1
    assert options["valueSize"] == 2
    assert options["valueFormat"] == 1

    client.async_send_command_no_wait.reset_mock()

    # Test setting parameter when one node has endpoint and other doesn't
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: [AIR_TEMPERATURE_SENSOR, "siren.indoor_siren_6_tone_id"],
            ATTR_ENDPOINT: 1,
            ATTR_CONFIG_PARAMETER: 32,
            ATTR_VALUE_SIZE: 2,
            ATTR_VALUE_FORMAT: 1,
            ATTR_CONFIG_VALUE: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 0
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.set_raw_config_parameter_value"
    assert args["nodeId"] == 2
    assert args["endpoint"] == 1
    options = args["options"]
    assert options["parameter"] == 32
    assert options["value"] == 1
    assert options["valueSize"] == 2
    assert options["valueFormat"] == 1

    client.async_send_command_no_wait.reset_mock()
    client.async_send_command.reset_mock()

    # Test groups get expanded
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[AIR_TEMPERATURE_SENSOR],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: "group.test",
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

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

    zwave_js_device_with_invalid_node_id = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={(DOMAIN, "500-500")}
    )

    non_zwave_js_entity = ent_reg.async_get_or_create(
        "test",
        "sensor",
        "test_sensor",
        suggested_object_id="test_sensor",
        config_entry=non_zwave_js_config_entry,
    )

    # Test unknown endpoint throws error when None are remaining
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
                ATTR_ENDPOINT: 5,
                ATTR_CONFIG_PARAMETER: 2,
                ATTR_VALUE_SIZE: 2,
                ATTR_VALUE_FORMAT: 1,
                ATTR_CONFIG_VALUE: 1,
            },
            blocking=True,
        )

    # Test that we can't include bitmask and value size and value format
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
                ATTR_CONFIG_PARAMETER: 102,
                ATTR_CONFIG_PARAMETER_BITMASK: 1,
                ATTR_CONFIG_VALUE: "Fahrenheit",
                ATTR_VALUE_FORMAT: 1,
                ATTR_VALUE_SIZE: 2,
            },
            blocking=True,
        )

    # Test that value size must be 1, 2, or 4 (not 3)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
                ATTR_CONFIG_PARAMETER: 102,
                ATTR_CONFIG_PARAMETER_BITMASK: 1,
                ATTR_CONFIG_VALUE: "Fahrenheit",
                ATTR_VALUE_FORMAT: 1,
                ATTR_VALUE_SIZE: 3,
            },
            blocking=True,
        )

    # Test that a Z-Wave JS device with an invalid node ID, non Z-Wave JS entity,
    # non Z-Wave JS device, invalid device_id, and invalid node_id gets filtered out.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG_PARAMETER,
        {
            ATTR_ENTITY_ID: [
                AIR_TEMPERATURE_SENSOR,
                non_zwave_js_entity.entity_id,
                "sensor.fake",
            ],
            ATTR_DEVICE_ID: [
                zwave_js_device_with_invalid_node_id.id,
                non_zwave_js_device.id,
                "fake_device_id",
            ],
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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

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
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting config parameter with no valid nodes raises Exception
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: "sensor.fake",
                ATTR_CONFIG_PARAMETER: 102,
                ATTR_CONFIG_PARAMETER_BITMASK: 1,
                ATTR_CONFIG_VALUE: 1,
            },
            blocking=True,
        )

    client.async_send_command_no_wait.reset_mock()
    client.async_send_command.reset_mock()

    caplog.clear()

    config_value = aeotec_zw164_siren.values["2-112-0-32"]
    cmd_result = SetConfigParameterResult("accepted", {"status": 255})

    # Test accepted return
    with patch(
        "homeassistant.components.zwave_js.services.Endpoint.async_set_raw_config_parameter_value",
        return_value=(config_value, cmd_result),
    ) as mock_set_raw_config_parameter_value:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: ["siren.indoor_siren_6_tone_id"],
                ATTR_ENDPOINT: 0,
                ATTR_CONFIG_PARAMETER: 32,
                ATTR_VALUE_SIZE: 2,
                ATTR_VALUE_FORMAT: 1,
                ATTR_CONFIG_VALUE: 1,
            },
            blocking=True,
        )
        assert len(mock_set_raw_config_parameter_value.call_args_list) == 1
        assert mock_set_raw_config_parameter_value.call_args[0][0] == 1
        assert mock_set_raw_config_parameter_value.call_args[0][1] == 32
        assert mock_set_raw_config_parameter_value.call_args[1] == {
            "property_key": None,
            "value_size": 2,
            "value_format": 1,
        }

    assert "Set configuration parameter" in caplog.text
    caplog.clear()

    # Test queued return
    cmd_result.status = "queued"
    with patch(
        "homeassistant.components.zwave_js.services.Endpoint.async_set_raw_config_parameter_value",
        return_value=(config_value, cmd_result),
    ) as mock_set_raw_config_parameter_value:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: ["siren.indoor_siren_6_tone_id"],
                ATTR_ENDPOINT: 0,
                ATTR_CONFIG_PARAMETER: 32,
                ATTR_VALUE_SIZE: 2,
                ATTR_VALUE_FORMAT: 1,
                ATTR_CONFIG_VALUE: 1,
            },
            blocking=True,
        )
        assert len(mock_set_raw_config_parameter_value.call_args_list) == 1
        assert mock_set_raw_config_parameter_value.call_args[0][0] == 1
        assert mock_set_raw_config_parameter_value.call_args[0][1] == 32
        assert mock_set_raw_config_parameter_value.call_args[1] == {
            "property_key": None,
            "value_size": 2,
            "value_format": 1,
        }

    assert "Added command to queue" in caplog.text
    caplog.clear()


async def test_set_config_parameter_gather(
    hass: HomeAssistant,
    client,
    multisensor_6,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test the set_config_parameter service gather functionality."""
    # Test setting config parameter by property and validate that the first node
    # which triggers an error doesn't prevent the second one to be called.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CONFIG_PARAMETER,
            {
                ATTR_ENTITY_ID: [
                    AIR_TEMPERATURE_SENSOR,
                    CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ],
                ATTR_CONFIG_PARAMETER: 1,
                ATTR_CONFIG_VALUE: 1,
            },
            blocking=True,
        )

    assert len(client.async_send_command_no_wait.call_args_list) == 0
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 26
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 112,
        "property": 1,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()


async def test_bulk_set_config_parameters(
    hass: HomeAssistant, client, multisensor_6, integration
) -> None:
    """Test the bulk_set_partial_config_parameters service."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, multisensor_6)}
    )
    assert device

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
        "endpoint": 0,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()

    # Test using area ID
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(device.id, area_id=area.id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_AREA_ID: area.id,
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
        "endpoint": 0,
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
        "endpoint": 0,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()

    # Test using hex values for config parameter values
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_ENTITY_ID: AIR_TEMPERATURE_SENSOR,
            ATTR_CONFIG_PARAMETER: 102,
            ATTR_CONFIG_VALUE: {
                1: "0x1",
                16: "0x1",
                32: "0x1",
                64: "0x1",
                128: "0x1",
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
        "endpoint": 0,
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
        "endpoint": 0,
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
        "endpoint": 0,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command.reset_mock()

    # Test groups get expanded
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[AIR_TEMPERATURE_SENSOR],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        {
            ATTR_ENTITY_ID: "group.test",
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
        "endpoint": 0,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command.reset_mock()


async def test_bulk_set_config_parameters_gather(
    hass: HomeAssistant,
    client,
    multisensor_6,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test the bulk_set_partial_config_parameters service gather functionality."""
    # Test bulk setting config parameter by property and validate that the first node
    # which triggers an error doesn't prevent the second one to be called.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
            {
                ATTR_ENTITY_ID: [
                    CLIMATE_RADIO_THERMOSTAT_ENTITY,
                    AIR_TEMPERATURE_SENSOR,
                ],
                ATTR_CONFIG_PARAMETER: 102,
                ATTR_CONFIG_VALUE: 241,
            },
            blocking=True,
        )

    assert len(client.async_send_command.call_args_list) == 0
    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
    }
    assert args["value"] == 241

    client.async_send_command_no_wait.reset_mock()


async def test_refresh_value(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test the refresh_value service."""
    # Test polling the primary value
    client.async_send_command.return_value = {"result": 2}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.poll_value"
    assert args["nodeId"] == 26
    assert args["valueId"] == {
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
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
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 8

    client.async_send_command.reset_mock()

    # Test polling all watched values using string for boolean
    client.async_send_command.return_value = {"result": 2}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_REFRESH_ALL_VALUES: "true",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 8

    client.async_send_command.reset_mock()

    # Test groups get expanded
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[CLIMATE_RADIO_THERMOSTAT_ENTITY],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    client.async_send_command.return_value = {"result": 2}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: "group.test",
            ATTR_REFRESH_ALL_VALUES: "true",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 8

    client.async_send_command.reset_mock()

    # Test polling against an invalid entity raises MultipleInvalid
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_VALUE,
            {ATTR_ENTITY_ID: "sensor.fake_entity_id"},
            blocking=True,
        )


async def test_set_value(
    hass: HomeAssistant, client, climate_danfoss_lc_13, integration
) -> None:
    """Test set_value service."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, climate_danfoss_lc_13)}
    )
    assert device

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
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
    }
    assert args["value"] == 2

    client.async_send_command_no_wait.reset_mock()

    # Test bitmask as value and non bool as bool
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_COMMAND_CLASS: 117,
            ATTR_PROPERTY: "local",
            ATTR_VALUE: "0x2",
            ATTR_WAIT_FOR_RESULT: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test using area ID
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(device.id, area_id=area.id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_AREA_ID: area.id,
            ATTR_COMMAND_CLASS: 117,
            ATTR_PROPERTY: "local",
            ATTR_VALUE: "0x2",
            ATTR_WAIT_FOR_RESULT: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test groups get expanded
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[CLIMATE_DANFOSS_LC13_ENTITY],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "group.test",
            ATTR_COMMAND_CLASS: 117,
            ATTR_PROPERTY: "local",
            ATTR_VALUE: "0x2",
            ATTR_WAIT_FOR_RESULT: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test that when a command fails we raise an exception
    client.async_send_command.return_value = {
        "result": {"status": 2, "message": "test"}
    }

    with pytest.raises(HomeAssistantError):
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
        "commandClass": 117,
        "endpoint": 0,
        "property": "local",
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test missing device and entities keys
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_COMMAND_CLASS: 117,
                ATTR_PROPERTY: "local",
                ATTR_VALUE: 2,
                ATTR_WAIT_FOR_RESULT: True,
            },
            blocking=True,
        )


async def test_set_value_string(
    hass: HomeAssistant, client, climate_danfoss_lc_13, lock_schlage_be469, integration
) -> None:
    """Test set_value service converts number to string when needed."""

    # Test that number gets converted to a string when needed
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            ATTR_COMMAND_CLASS: 99,
            ATTR_PROPERTY: "userCode",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: 12345,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == lock_schlage_be469.node_id
    assert args["valueId"] == {
        "commandClass": 99,
        "endpoint": 0,
        "property": "userCode",
        "propertyKey": 1,
    }
    assert args["value"] == "12345"


async def test_set_value_options(
    hass: HomeAssistant, client, aeon_smart_switch_6, integration
) -> None:
    """Test set_value service with options."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: AEON_SMART_SWITCH_LIGHT_ENTITY,
            ATTR_COMMAND_CLASS: 37,
            ATTR_PROPERTY: "targetValue",
            ATTR_VALUE: 2,
            ATTR_OPTIONS: {"transitionDuration": 1},
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == aeon_smart_switch_6.node_id
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 37,
        "property": "targetValue",
    }
    assert args["value"] == 2
    assert args["options"] == {"transitionDuration": 1}

    client.async_send_command.reset_mock()


async def test_set_value_gather(
    hass: HomeAssistant,
    client,
    multisensor_6,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test the set_value service gather functionality."""
    # Test setting value by property and validate that the first node
    # which triggers an error doesn't prevent the second one to be called.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: [
                    CLIMATE_RADIO_THERMOSTAT_ENTITY,
                    AIR_TEMPERATURE_SENSOR,
                ],
                ATTR_COMMAND_CLASS: 112,
                ATTR_PROPERTY: 102,
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 1,
            },
            blocking=True,
        )

    assert len(client.async_send_command.call_args_list) == 0
    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()


async def test_multicast_set_value(
    hass: HomeAssistant,
    client,
    climate_danfoss_lc_13,
    climate_eurotronic_spirit_z,
    integration,
) -> None:
    """Test multicast_set_value service."""
    # Test successful multicast call
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_ENTITY_ID: [
                CLIMATE_DANFOSS_LC13_ENTITY,
                CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
            ],
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: 2,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "multicast_group.set_value"
    assert args["nodeIDs"] == [
        climate_eurotronic_spirit_z.node_id,
        climate_danfoss_lc_13.node_id,
    ]
    assert args["valueId"] == {
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test successful multicast call with hex value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_ENTITY_ID: [
                CLIMATE_DANFOSS_LC13_ENTITY,
                CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
            ],
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: "0x2",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "multicast_group.set_value"
    assert args["nodeIDs"] == [
        climate_eurotronic_spirit_z.node_id,
        climate_danfoss_lc_13.node_id,
    ]
    assert args["valueId"] == {
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test using area ID
    dev_reg = async_get_dev_reg(hass)
    device_eurotronic = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, climate_eurotronic_spirit_z)}
    )
    assert device_eurotronic
    device_danfoss = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, climate_danfoss_lc_13)}
    )
    assert device_danfoss
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(device_eurotronic.id, area_id=area.id)
    dev_reg.async_update_device(device_danfoss.id, area_id=area.id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_AREA_ID: area.id,
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: "0x2",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "multicast_group.set_value"
    assert args["nodeIDs"] == [
        climate_eurotronic_spirit_z.node_id,
        climate_danfoss_lc_13.node_id,
    ]
    assert args["valueId"] == {
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test groups get expanded for multicast call
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[CLIMATE_DANFOSS_LC13_ENTITY, CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_ENTITY_ID: "group.test",
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: "0x2",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "multicast_group.set_value"
    assert args["nodeIDs"] == [
        climate_eurotronic_spirit_z.node_id,
        climate_danfoss_lc_13.node_id,
    ]
    assert args["valueId"] == {
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test successful broadcast call
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_BROADCAST: True,
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: 2,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "broadcast_node.set_value"
    assert args["valueId"] == {
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test sending one node without broadcast uses the node.set_value command instead
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_COMMAND_CLASS: 67,
            ATTR_PROPERTY: "setpoint",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: 2,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"

    client.async_send_command_no_wait.reset_mock()

    # Test no device, entity, or broadcast flag raises error
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MULTICAST_SET_VALUE,
            {
                ATTR_COMMAND_CLASS: 67,
                ATTR_PROPERTY: "setpoint",
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )

    # Test that when a command is unsuccessful we raise an exception
    client.async_send_command.return_value = {
        "result": {"status": 2, "message": "test"}
    }

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MULTICAST_SET_VALUE,
            {
                ATTR_ENTITY_ID: [
                    CLIMATE_DANFOSS_LC13_ENTITY,
                    CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
                ],
                ATTR_COMMAND_CLASS: 67,
                ATTR_PROPERTY: "setpoint",
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )

    client.async_send_command.reset_mock()

    # Test that when we get an exception from the library we raise an exception
    client.async_send_command.side_effect = FailedZWaveCommand("test", 12, "test")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MULTICAST_SET_VALUE,
            {
                ATTR_ENTITY_ID: [
                    CLIMATE_DANFOSS_LC13_ENTITY,
                    CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
                ],
                ATTR_COMMAND_CLASS: 67,
                ATTR_PROPERTY: "setpoint",
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )

    client.async_send_command.reset_mock()

    # Create a fake node with a different home ID from a real node and patch it into
    # return of helper function to check the validation for two nodes having different
    # home IDs
    diff_network_node = MagicMock()
    diff_network_node.client.driver.controller.home_id.return_value = "diff_home_id"

    with (
        pytest.raises(vol.MultipleInvalid),
        patch(
            "homeassistant.components.zwave_js.helpers.async_get_node_from_device_id",
            side_effect=(climate_danfoss_lc_13, diff_network_node),
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MULTICAST_SET_VALUE,
            {
                ATTR_ENTITY_ID: [
                    CLIMATE_DANFOSS_LC13_ENTITY,
                ],
                ATTR_DEVICE_ID: "fake_device_id",
                ATTR_COMMAND_CLASS: 67,
                ATTR_PROPERTY: "setpoint",
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )

    # Test that when there are multiple zwave_js config entries, service will fail
    # without devices or entities
    new_entry = MockConfigEntry(domain=DOMAIN)
    new_entry.add_to_hass(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MULTICAST_SET_VALUE,
            {
                ATTR_BROADCAST: True,
                ATTR_COMMAND_CLASS: 67,
                ATTR_PROPERTY: "setpoint",
                ATTR_PROPERTY_KEY: 1,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )


async def test_multicast_set_value_options(
    hass: HomeAssistant,
    client,
    bulb_6_multi_color,
    light_color_null_values,
    integration,
) -> None:
    """Test multicast_set_value service with options."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_ENTITY_ID: [
                BULB_6_MULTI_COLOR_LIGHT_ENTITY,
                "light.repeater",
            ],
            ATTR_COMMAND_CLASS: 51,
            ATTR_PROPERTY: "targetColor",
            ATTR_VALUE: (
                '{ "warmWhite": 0, "coldWhite": 0, "red": 255, "green": 0, "blue": 0 }'
            ),
            ATTR_OPTIONS: {"transitionDuration": 1},
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "multicast_group.set_value"
    assert args["nodeIDs"] == [
        bulb_6_multi_color.node_id,
        light_color_null_values.node_id,
    ]
    assert args["valueId"] == {
        "commandClass": 51,
        "property": "targetColor",
    }
    assert (
        args["value"]
        == '{ "warmWhite": 0, "coldWhite": 0, "red": 255, "green": 0, "blue": 0 }'
    )
    assert args["options"] == {"transitionDuration": 1}

    client.async_send_command.reset_mock()


async def test_multicast_set_value_string(
    hass: HomeAssistant,
    client,
    lock_id_lock_as_id150,
    lock_schlage_be469,
    integration,
) -> None:
    """Test multicast_set_value service converts number to string when needed."""
    client.async_send_command.return_value = {"result": {"status": 255}}

    # Test that number gets converted to a string when needed
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MULTICAST_SET_VALUE,
        {
            ATTR_BROADCAST: True,
            ATTR_COMMAND_CLASS: 99,
            ATTR_PROPERTY: "userCode",
            ATTR_PROPERTY_KEY: 1,
            ATTR_VALUE: 12345,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "broadcast_node.set_value"
    assert args["valueId"] == {
        "commandClass": 99,
        "property": "userCode",
        "propertyKey": 1,
    }
    assert args["value"] == "12345"


async def test_ping(
    hass: HomeAssistant,
    client,
    climate_danfoss_lc_13,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test ping service."""
    dev_reg = async_get_dev_reg(hass)
    device_radio_thermostat = dev_reg.async_get_device(
        identifiers={
            get_device_id(
                client.driver, climate_radio_thermostat_ct100_plus_different_endpoints
            )
        }
    )
    assert device_radio_thermostat
    device_danfoss = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, climate_danfoss_lc_13)}
    )
    assert device_danfoss

    client.async_send_command.return_value = {"responded": True}

    # Test successful ping call
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PING,
        {
            ATTR_ENTITY_ID: [
                CLIMATE_DANFOSS_LC13_ENTITY,
                CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ],
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.ping"
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()

    # Test successful ping call with devices
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PING,
        {
            ATTR_DEVICE_ID: [
                device_radio_thermostat.id,
                device_danfoss.id,
            ],
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.ping"
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()

    # Test successful ping call with area
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(device_radio_thermostat.id, area_id=area.id)
    dev_reg.async_update_device(device_danfoss.id, area_id=area.id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PING,
        {ATTR_AREA_ID: area.id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.ping"
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()

    # Test groups get expanded for multicast call
    assert await async_setup_component(hass, "group", {})
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=[CLIMATE_DANFOSS_LC13_ENTITY, CLIMATE_RADIO_THERMOSTAT_ENTITY],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PING,
        {
            ATTR_ENTITY_ID: "group.test",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.ping"
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()

    # Test no device or entity raises error
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PING,
            {},
            blocking=True,
        )

    client.async_send_command.reset_mock()
    client.async_send_command.side_effect = FailedZWaveCommand("test", 1, "test")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PING,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            },
            blocking=True,
        )


async def test_invoke_cc_api(
    hass: HomeAssistant,
    client,
    climate_danfoss_lc_13,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test invoke_cc_api service."""
    dev_reg = async_get_dev_reg(hass)
    device_radio_thermostat = dev_reg.async_get_device(
        identifiers={
            get_device_id(
                client.driver, climate_radio_thermostat_ct100_plus_different_endpoints
            )
        }
    )
    assert device_radio_thermostat
    device_danfoss = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, climate_danfoss_lc_13)}
    )
    assert device_danfoss

    # Test successful invoke_cc_api call with a static endpoint
    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.return_value = {"response": True}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INVOKE_CC_API,
        {
            ATTR_DEVICE_ID: [
                device_radio_thermostat.id,
                device_danfoss.id,
            ],
            ATTR_COMMAND_CLASS: 67,
            ATTR_ENDPOINT: 0,
            ATTR_METHOD_NAME: "someMethod",
            ATTR_PARAMETERS: [1, 2],
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()

    # Test successful invoke_cc_api call without an endpoint (include area)
    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(device_danfoss.id, area_id=area.id)

    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.return_value = {"response": True}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INVOKE_CC_API,
        {
            ATTR_AREA_ID: area.id,
            ATTR_DEVICE_ID: [
                device_radio_thermostat.id,
                "fake_device_id",
            ],
            ATTR_ENTITY_ID: [
                "sensor.not_real",
                "select.living_connect_z_thermostat_local_protection_state",
                "sensor.living_connect_z_thermostat_node_status",
            ],
            ATTR_COMMAND_CLASS: 67,
            ATTR_METHOD_NAME: "someMethod",
            ATTR_PARAMETERS: [1, 2],
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()

    # Test failed invoke_cc_api call on one node. We return the error on
    # the first node in the call to make sure that gather works as expected
    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.side_effect = FailedZWaveCommand(
        "test", 12, "test"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INVOKE_CC_API,
            {
                ATTR_DEVICE_ID: [
                    device_danfoss.id,
                    device_radio_thermostat.id,
                ],
                ATTR_COMMAND_CLASS: 67,
                ATTR_ENDPOINT: 0,
                ATTR_METHOD_NAME: "someMethod",
                ATTR_PARAMETERS: [1, 2],
            },
            blocking=True,
        )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 67
    assert args["endpoint"] == 0
    assert args["methodName"] == "someMethod"
    assert args["args"] == [1, 2]
    assert args["nodeId"] == climate_danfoss_lc_13.node_id

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()


async def test_refresh_notifications(
    hass: HomeAssistant, client, zen_31, multisensor_6, integration
) -> None:
    """Test refresh_notifications service."""
    dev_reg = async_get_dev_reg(hass)
    zen_31_device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, zen_31)}
    )
    assert zen_31_device
    multisensor_6_device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, multisensor_6)}
    )
    assert multisensor_6_device

    area_reg = async_get_area_reg(hass)
    area = area_reg.async_get_or_create("test")
    dev_reg.async_update_device(zen_31_device.id, area_id=area.id)

    # Test successful refresh_notifications call
    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.return_value = {"response": True}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_NOTIFICATIONS,
        {
            ATTR_AREA_ID: area.id,
            ATTR_DEVICE_ID: [zen_31_device.id, multisensor_6_device.id],
            ATTR_NOTIFICATION_TYPE: 1,
            ATTR_NOTIFICATION_EVENT: 2,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 113
    assert args["endpoint"] == 0
    assert args["methodName"] == "get"
    assert args["args"] == [{"notificationType": 1, "notificationEvent": 2}]
    assert args["nodeId"] == zen_31.node_id

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 113
    assert args["endpoint"] == 0
    assert args["methodName"] == "get"
    assert args["args"] == [{"notificationType": 1, "notificationEvent": 2}]
    assert args["nodeId"] == multisensor_6.node_id

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()

    # Test failed refresh_notifications call on one node. We return the error on
    # the first node in the call to make sure that gather works as expected
    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.side_effect = FailedZWaveCommand(
        "test", 12, "test"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_NOTIFICATIONS,
            {
                ATTR_DEVICE_ID: [multisensor_6_device.id, zen_31_device.id],
                ATTR_NOTIFICATION_TYPE: 1,
            },
            blocking=True,
        )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 113
    assert args["endpoint"] == 0
    assert args["methodName"] == "get"
    assert args["args"] == [{"notificationType": 1}]
    assert args["nodeId"] == zen_31.node_id

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["commandClass"] == 113
    assert args["endpoint"] == 0
    assert args["methodName"] == "get"
    assert args["args"] == [{"notificationType": 1}]
    assert args["nodeId"] == multisensor_6.node_id

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()
