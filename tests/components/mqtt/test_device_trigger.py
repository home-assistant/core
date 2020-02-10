"""The tests for MQTT device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.mqtt import DOMAIN
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_fire_mqtt_message,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test we get the expected triggers from a discovered mqtt device."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "topic": "foobar/triggers/button1",
            "payload": "short_press",
            "qos": 0,
            "type": "button_short_press",
            "subtype": "button_1",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, calls, mqtt_mock):
    """Test for turn_on and turn_off triggers firing."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "topic": "foobar/triggers/button1",
                        "payload": "short_press",
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
                        "device_id": "",
                        "topic": "foobar/triggers/button1",
                        "payload": "long_press",
                        "type": "button_short_press",
                        "subtype": "button_1",
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
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"
