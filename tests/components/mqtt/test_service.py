"""The tests for the MQTT service platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from voluptuous import MultipleInvalid

from homeassistant.components import mqtt
from homeassistant.components.mqtt.service import PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps

from tests.common import async_fire_mqtt_message

SERVICE_DOMAIN = "service"

DEFAULT_PARAMETER_SCHEMA = [
    {
        "name": "message",
        "description": "Enter a text",
        "type": "string",
        "required": True,
    },
    {
        "name": "happy",
        "description": "Select for happy mode",
        "type": "bool",
        "exclusive": "happyness",
    },
    {
        "name": "letter",
        "description": "Select one or more letters",
        "type": "select",
        "example": "a",
        "multiple": True,
        "custom_value": True,
        "options": ["a", "b", "c"],
        "inclusive": "selectors",
    },
    {
        "name": "color",
        "description": "Select a color",
        "type": "dropdown",
        "example": "Red",
        "options": [
            {"value": "r", "label": "Red"},
            {"value": "g", "label": "Green"},
            {"value": "b", "label": "Blue"},
        ],
        "inclusive": "selectors",
    },
]

DEFAULT_COMMAND_TEMPLATE = (
    "{"
    '"message": "{{ message }}", '
    '"happy": {{ happy }}, '
    '"letter": {{ letter }}, '
    '"color": "{{ color[0] if color else "" }}" '
    "}"
)

DEFAULT_CONFIG_PAYLOAD = {
    "name": "Test service",
    "description": "Test service for a demo",
    "command_topic": "test/cmdservice",
    "command_template": DEFAULT_COMMAND_TEMPLATE,
    "schema": DEFAULT_PARAMETER_SCHEMA,
}

DEFAULT_DISCOVERY_TOPIC = f"homeassistant/{SERVICE_DOMAIN}/bla/config"
ALTERNATE_DISCOVERY_TOPIC = f"homeassistant/{SERVICE_DOMAIN}/other/config"

DEFAULT_SERVICE_NAME = "test_service"


@pytest.fixture(autouse=True)
def skip_platform_setup() -> None:
    """Skip setup platforms to speed up test."""
    with patch("homeassistant.components.mqtt.PLATFORMS", []):
        yield


async def async_call_service(
    hass: HomeAssistant, service_name: str, data: dict[str, Any] | None
) -> None:
    """Call the custom MQTT service."""
    await hass.services.async_call(
        mqtt.DOMAIN,
        service_name,
        data,
        blocking=True,
    )


async def test_custom_service(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config
) -> None:
    """Test a custom discovered MQTT service."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    publish_mock: AsyncMock = mqtt_mock.async_publish

    async_fire_mqtt_message(
        hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
    )
    await hass.async_block_till_done()

    assert DEFAULT_SERVICE_NAME in hass.services.async_services()[mqtt.DOMAIN].keys()

    data = {
        "message": "This is in important message",
        "happy": True,
        "letter": ["a"],
        "color": "r",
    }

    # test with all parameters
    await async_call_service(hass, DEFAULT_SERVICE_NAME, data)
    await hass.async_block_till_done()
    publish_mock.assert_called_once_with(
        "test/cmdservice",
        '{"message": "This is in important message", '
        '"happy": True, "letter": [\'a\'], "color": "r" }',
        0,
        False,
    )
    publish_mock.reset_mock()

    # test with required parameters
    data2 = deepcopy(data)
    data2.pop("letter")
    data2.pop("color")
    data2.pop("happy")
    await async_call_service(hass, DEFAULT_SERVICE_NAME, data2)
    await hass.async_block_till_done()
    publish_mock.assert_called_once_with(
        "test/cmdservice",
        '{"message": "This is in important message", '
        '"happy": None, "letter": None, "color": "" }',
        0,
        False,
    )
    publish_mock.reset_mock()

    # test without all required parameters
    data2 = deepcopy(data)
    data2.pop("message")
    with pytest.raises(MultipleInvalid):
        await async_call_service(hass, DEFAULT_SERVICE_NAME, data2)
        await hass.async_block_till_done()
    publish_mock.assert_not_called()
    publish_mock.reset_mock()

    # test with different QoS and retain
    config2 = deepcopy(DEFAULT_CONFIG_PAYLOAD)
    config2["qos"] = 1
    config2["retain"] = True
    async_fire_mqtt_message(hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(config2))
    await hass.async_block_till_done()

    await async_call_service(hass, DEFAULT_SERVICE_NAME, data)
    await hass.async_block_till_done()
    publish_mock.assert_called_once_with(
        "test/cmdservice",
        '{"message": "This is in important message", '
        '"happy": True, "letter": [\'a\'], "color": "r" }',
        1,
        True,
    )
    publish_mock.reset_mock()


async def test_invalid_option_config_for_selectors() -> None:
    """Test option validation on select selector."""
    no_options_arg = [
        {
            "name": "letter",
            "description": "Select one or more letters",
            "type": "select",
            "example": "a",
            "multiple": True,
            "custom_value": True,
            "options": [],
        }
    ]
    config = deepcopy(DEFAULT_CONFIG_PAYLOAD)
    config["schema"] = no_options_arg

    with pytest.raises(MultipleInvalid) as exc_info:
        PLATFORM_SCHEMA(config)
    assert exc_info.value.msg == "Required options are missing"


async def test_discovery_with_duplicate_name(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config, caplog
) -> None:
    """Test discovery and removal of discovered service."""
    await mqtt_mock_entry_no_yaml_config()

    async_fire_mqtt_message(
        hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
    )
    await hass.async_block_till_done()
    assert DEFAULT_SERVICE_NAME in hass.services.async_services()[mqtt.DOMAIN].keys()

    async_fire_mqtt_message(
        hass, ALTERNATE_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
    )
    await hass.async_block_till_done()

    assert f"Service '{DEFAULT_SERVICE_NAME}' is already registered" in caplog.text


async def test_discovery_and_removal_service(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config
) -> None:
    """Test discovery and removal of discovered service."""
    await mqtt_mock_entry_no_yaml_config()

    async_fire_mqtt_message(
        hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
    )
    await hass.async_block_till_done()
    assert DEFAULT_SERVICE_NAME in hass.services.async_services()[mqtt.DOMAIN].keys()

    async_fire_mqtt_message(hass, DEFAULT_DISCOVERY_TOPIC, "")
    await hass.async_block_till_done()
    assert (
        DEFAULT_SERVICE_NAME not in hass.services.async_services()[mqtt.DOMAIN].keys()
    )


async def test_discovery_update_unchanged_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config
) -> None:
    """Test update of discovered update."""
    await mqtt_mock_entry_no_yaml_config()
    with patch(
        "homeassistant.components.mqtt.service.MQTTService.async_update"
    ) as discovery_update:
        async_fire_mqtt_message(
            hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
        )
        await hass.async_block_till_done()
        async_fire_mqtt_message(
            hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(DEFAULT_CONFIG_PAYLOAD)
        )
        await hass.async_block_till_done()
        assert discovery_update.call_count == 0


async def test_discovery_update_service(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config, caplog
) -> None:
    """Test update of discovered service."""
    config1 = DEFAULT_CONFIG_PAYLOAD
    config2 = deepcopy(DEFAULT_CONFIG_PAYLOAD)
    config2["name"] = "Service name update"

    await mqtt_mock_entry_no_yaml_config()
    with patch(
        "homeassistant.components.mqtt.service.MQTTService.async_update"
    ) as discovery_update:
        async_fire_mqtt_message(hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(config1))
        await hass.async_block_till_done()
        async_fire_mqtt_message(hass, DEFAULT_DISCOVERY_TOPIC, json_dumps(config2))
        await hass.async_block_till_done()
        assert discovery_update.call_count == 1
