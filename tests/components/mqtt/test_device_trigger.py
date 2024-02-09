"""The tests for MQTT device triggers."""
import json
from unittest.mock import patch

import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.mqtt import _LOGGER, DOMAIN, debug_info
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.setup import async_setup_component

from .test_common import help_test_unload_config_entry

from tests.common import (
    async_fire_mqtt_message,
    async_get_device_automations,
    async_mock_service,
)
from tests.typing import MqttMockHAClient, MqttMockHAClientGenerator, WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def binary_sensor_and_sensor_only():
    """Only setup the binary_sensor and sensor platform to speed up tests."""
    with patch(
        "homeassistant.components.mqtt.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.SENSOR],
    ):
        yield


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test we get the expected triggers from a discovered mqtt device."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_unknown_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test we don't get unknown triggers."""
    await mqtt_mock_entry()
    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []


async def test_get_non_existing_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test getting non existing triggers."""
    await mqtt_mock_entry()
    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []


@pytest.mark.no_fail_on_log_exception
async def test_discover_bad_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test bad discovery message."""
    await mqtt_mock_entry()
    # Test sending bad data
    data0 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payloads": "short_press",'
        '  "topics": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data0)
    await hass.async_block_till_done()
    assert device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")}) is None

    # Test sending correct data
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_update_remove_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test triggers can be updated and removed."""
    await mqtt_mock_entry()
    config1 = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"], "name": "milk"},
        "payload": "short_press",
        "topic": "foobar/triggers/button1",
        "type": "button_short_press",
        "subtype": "button_1",
    }
    config1["some_future_option_1"] = "future_option_1"
    data1 = json.dumps(config1)

    config2 = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"], "name": "beer"},
        "payload": "short_press",
        "topic": "foobar/triggers/button1",
        "type": "button_short_press",
        "subtype": "button_1",
    }
    config2["topic"] = "foobar/tag_scanned2"
    data2 = json.dumps(config2)

    config3 = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"], "name": "beer"},
        "payload": "short_press",
        "topic": "foobar/triggers/button1",
        "type": "button_short_press",
        "subtype": "button_2",
    }
    config3["topic"] = "foobar/tag_scanned2"
    data3 = json.dumps(config3)

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry.name == "milk"
    expected_triggers1 = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    expected_triggers2 = [dict(expected_triggers1[0])]
    expected_triggers2[0]["subtype"] = "button_2"

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers1)
    assert device_entry.name == "milk"

    # Update trigger topic
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data2)
    await hass.async_block_till_done()
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers1)
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry.name == "beer"

    # Update trigger type / subtype
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data3)
    await hass.async_block_till_done()
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers2)

    # Remove trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None


async def test_if_fires_on_mqtt_message(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test triggers firing."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button2",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_long_press",
                        "subtype": "button_2",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button2", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_discovery_id_is_prefered(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test if discovery is preferred over referencing by type/subtype.

    The use of CONF_DISCOVERY_ID was deprecated in HA Core 2024.2.
    By default, a MQTT device trigger now will be referenced by
    device_id, type and subtype instead.
    If discovery_id is found an an automation it will have a higher
    priority and than type and subtype.
    """
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    # type and subtype of data 2 do not match with the type and subtype
    # in the automation, because discovery_id matches, the trigger will fire
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "completely_different_type",
                        "subtype": "completely_different_sub_type",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    # Fake short press, matching on type and subtype
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press, matching on discovery_id
    calls.clear()
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "long_press"


async def test_non_unique_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test non unique triggers."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"], "name": "milk"},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "press",'
        '  "subtype": "button" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"], "name": "beer"},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button2",'
        '  "type": "press",'
        '  "subtype": "button" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry.name == "milk"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    # The device entry was updated, but the trigger was not unique
    # and therefore it was not set up.
    assert device_entry.name == "beer"
    assert (
        "Config for device trigger bla2 conflicts with existing device trigger, cannot set up trigger"
        in caplog.text
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "press",
                        "subtype": "button",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("press1")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "press",
                        "subtype": "button",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("press2")},
                    },
                },
            ]
        },
    )

    # Try to trigger first config.
    # and triggers both attached instances.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data["some"] == "press1"
    assert calls[1].data["some"] == "press2"

    # Trigger second config references to same trigger
    # and triggers both attached instances.
    async_fire_mqtt_message(hass, "foobar/triggers/button2", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data["some"] == "press1"
    assert calls[1].data["some"] == "press2"

    # Removing the first trigger will clean up
    calls.clear()
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert (
        "Device trigger ('device_automation', 'bla1') has been removed" in caplog.text
    )
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    assert len(calls) == 0


async def test_if_fires_on_mqtt_message_template(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test triggers firing with a message template and a shared topic."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        "  \"payload\": \"{{ 'foo_press'|regex_replace('foo', 'short') }}\","
        '  "topic": "foobar/triggers/button{{ sqrt(16)|round }}",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1",'
        '  "value_template": "{{ value_json.button }}"}'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        "  \"payload\": \"{{ 'foo_press'|regex_replace('foo', 'long') }}\","
        '  "topic": "foobar/triggers/button{{ sqrt(16)|round }}",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2",'
        '  "value_template": "{{ value_json.button }}"}'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_long_press",
                        "subtype": "button_2",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button4", '{"button":"short_press"}')
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button4", '{"button":"long_press"}')
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_fires_on_mqtt_message_late_discover(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test triggers firing of MQTT device triggers discovered after setup."""
    await mqtt_mock_entry()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button2",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_long_press",
                        "subtype": "button_2",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button2", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_fires_on_mqtt_message_after_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test triggers firing after update."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_2" }'
    )
    data3 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/buttonOne",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Update the trigger with existing type/subtype change
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data1)
    await hass.async_block_till_done()
    assert "Cannot update device trigger ('device_automation', 'bla2')" in caplog.text

    # Update the trigger with different topic
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data3)
    await hass.async_block_till_done()

    calls.clear()
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 0

    calls.clear()
    async_fire_mqtt_message(hass, "foobar/triggers/buttonOne", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Update the trigger with same topic
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data3)
    await hass.async_block_till_done()

    calls.clear()
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 0

    calls.clear()
    async_fire_mqtt_message(hass, "foobar/triggers/buttonOne", "")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_no_resubscribe_same_topic(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test subscription to topics without change."""
    mqtt_mock = await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    call_count = mqtt_mock.async_subscribe.call_count
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    assert mqtt_mock.async_subscribe.call_count == call_count


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test triggers not firing after removal."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove the trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Rediscover the trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_not_fires_on_mqtt_message_after_remove_from_registry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    calls: list[ServiceCall],
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test triggers not firing after removal."""
    assert await async_setup_component(hass, "config", {})
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await mqtt_mock_entry()

    ws_client = await hass_ws_client(hass)

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mqtt_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test attach and removal of trigger."""
    await mqtt_mock_entry()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "short_press"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test attach and removal of trigger ."""
    await mqtt_mock_entry()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "short_press"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test attach and removal of trigger ."""
    await mqtt_mock_entry()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Try to remove the trigger twice
    with pytest.raises(HomeAssistantError):
        remove()


async def test_entity_device_info_with_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT device registry integration."""
    await mqtt_mock_entry()

    data = json.dumps(
        {
            "automation_type": "trigger",
            "topic": "test-topic",
            "type": "foo",
            "subtype": "bar",
            "device": {
                "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "hw_version": "rev1",
                "serial_number": "1234deadbeef",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.serial_number == "1234deadbeef"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT device registry integration."""
    await mqtt_mock_entry()

    data = json.dumps(
        {
            "automation_type": "trigger",
            "topic": "test-topic",
            "type": "foo",
            "subtype": "bar",
            "device": {
                "identifiers": ["helloworld"],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "hw_version": "rev1",
                "serial_number": "1234deadbeef",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.serial_number == "1234deadbeef"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test device registry update."""
    await mqtt_mock_entry()

    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {
            "identifiers": ["helloworld"],
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "serial_number": "1234deadbeef",
            "sw_version": "0.1-beta",
        },
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def test_cleanup_trigger(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test trigger discovery topic is cleaned when device is removed from registry."""
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers[0]["type"] == "foo"

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mqtt_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is None

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/device_automation/bla/config", "", 0, True
    )


async def test_cleanup_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test removal from device registry when trigger is removed."""
    await mqtt_mock_entry()
    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers[0]["type"] == "foo"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is None


async def test_cleanup_device_several_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test removal from device registry when the last trigger is removed."""
    await mqtt_mock_entry()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo2",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 2
    assert triggers[0]["type"] == "foo"
    assert triggers[1]["type"] == "foo2"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1
    assert triggers[0]["type"] == "foo2"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is None


async def test_cleanup_device_with_entity1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test removal from device registry for device with entity.

    Trigger removed first, then entity.
    """
    await mqtt_mock_entry()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 2  # 2 binary_sensor triggers

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is None


async def test_cleanup_device_with_entity2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test removal from device registry for device with entity.

    Entity removed first, then trigger.
    """
    await mqtt_mock_entry()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1  # device trigger

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "helloworld")}
    )
    assert device_entry is None


async def test_trigger_debug_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry()

    config1 = {
        "platform": "mqtt",
        "automation_type": "trigger",
        "topic": "test-topic1",
        "type": "foo",
        "subtype": "bar1",
        "device": {
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
    }
    config2 = {
        "platform": "mqtt",
        "automation_type": "trigger",
        "topic": "test-topic2",
        "type": "foo",
        "subtype": "bar2",
        "device": {
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
        },
    }
    data = json.dumps(config1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data)
    data = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 2
    topic_map = {
        "homeassistant/device_automation/bla1/config": config1,
        "homeassistant/device_automation/bla2/config": config2,
    }
    assert (
        topic_map[debug_info_data["triggers"][0]["discovery_data"]["topic"]]
        != topic_map[debug_info_data["triggers"][1]["discovery_data"]["topic"]]
    )
    assert (
        debug_info_data["triggers"][0]["discovery_data"]["payload"]
        == topic_map[debug_info_data["triggers"][0]["discovery_data"]["topic"]]
    )
    assert (
        debug_info_data["triggers"][1]["discovery_data"]["payload"]
        == topic_map[debug_info_data["triggers"][1]["discovery_data"]["topic"]]
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()
    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 1
    assert (
        debug_info_data["triggers"][0]["discovery_data"]["topic"]
        == "homeassistant/device_automation/bla2/config"
    )
    assert debug_info_data["triggers"][0]["discovery_data"]["payload"] == config2


async def test_unload_entry(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unloading the MQTT entry."""

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press 1
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await help_test_unload_config_entry(hass)

    # Rediscover message and fake short press 2 (non impact)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Start entry again
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    await hass.config_entries.async_setup(mqtt_entry.entry_id)

    # Rediscover and fake short press 3
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
