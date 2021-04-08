"""The tests for MQTT tag scanner."""
import copy
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.helpers import device_registry as dr

from tests.common import (
    async_fire_mqtt_message,
    async_get_device_automations,
    mock_device_registry,
    mock_registry,
)

DEFAULT_CONFIG_DEVICE = {
    "device": {"identifiers": ["0AFFD2"]},
    "topic": "foobar/tag_scanned",
}

DEFAULT_CONFIG = {
    "topic": "foobar/tag_scanned",
}

DEFAULT_CONFIG_JSON = {
    "device": {"identifiers": ["0AFFD2"]},
    "topic": "foobar/tag_scanned",
    "value_template": "{{ value_json.PN532.UID }}",
}

DEFAULT_TAG_ID = "E9F35959"

DEFAULT_TAG_SCAN = "E9F35959"

DEFAULT_TAG_SCAN_JSON = (
    '{"Time":"2020-09-28T17:02:10","PN532":{"UID":"E9F35959", "DATA":"ILOVETASMOTA"}}'
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
def tag_mock():
    """Fixture to mock tag."""
    with patch("homeassistant.components.tag.async_scan_tag") as mock_tag:
        yield mock_tag


@pytest.mark.no_fail_on_log_exception
async def test_discover_bad_tag(hass, device_reg, entity_reg, mqtt_mock, tag_mock):
    """Test bad discovery message."""
    config1 = copy.deepcopy(DEFAULT_CONFIG_DEVICE)

    # Test sending bad data
    data0 = '{ "device":{"identifiers":["0AFFD2"]}, "topics": "foobar/tag_scanned" }'
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data0)
    await hass.async_block_till_done()
    assert device_reg.async_get_device({("mqtt", "0AFFD2")}) is None

    # Test sending correct data
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_if_fires_on_mqtt_message_with_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning, with device."""
    config = copy.deepcopy(DEFAULT_CONFIG_DEVICE)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_if_fires_on_mqtt_message_without_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning, without device."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)


async def test_if_fires_on_mqtt_message_with_template(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning, with device."""
    config = copy.deepcopy(DEFAULT_CONFIG_JSON)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN_JSON)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_strip_tag_id(hass, device_reg, mqtt_mock, tag_mock):
    """Test strip whitespace from tag_id."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", "123456   ")
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, "123456", None)


async def test_if_fires_on_mqtt_message_after_update_with_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning after update."""
    config1 = copy.deepcopy(DEFAULT_CONFIG_DEVICE)
    config2 = copy.deepcopy(DEFAULT_CONFIG_DEVICE)
    config2["topic"] = "foobar/tag_scanned2"

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config1))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Update the tag scanner with different topic
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned2", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Update the tag scanner with same topic
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned2", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_if_fires_on_mqtt_message_after_update_without_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning after update."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["topic"] = "foobar/tag_scanned2"

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config1))
    await hass.async_block_till_done()

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)

    # Update the tag scanner with different topic
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned2", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)

    # Update the tag scanner with same topic
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned2", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)


async def test_if_fires_on_mqtt_message_after_update_with_template(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning after update."""
    config1 = copy.deepcopy(DEFAULT_CONFIG_JSON)
    config2 = copy.deepcopy(DEFAULT_CONFIG_JSON)
    config2["value_template"] = "{{ value_json.RDM6300.UID }}"
    tag_scan_2 = '{"Time":"2020-09-28T17:02:10","RDM6300":{"UID":"E9F35959", "DATA":"ILOVETASMOTA"}}'

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config1))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN_JSON)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Update the tag scanner with different template
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN_JSON)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", tag_scan_2)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Update the tag scanner with same template
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config2))
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN_JSON)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", tag_scan_2)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_no_resubscribe_same_topic(hass, device_reg, mqtt_mock):
    """Test subscription to topics without change."""
    config = copy.deepcopy(DEFAULT_CONFIG_DEVICE)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    assert device_reg.async_get_device({("mqtt", "0AFFD2")})

    call_count = mqtt_mock.async_subscribe.call_count
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    assert mqtt_mock.async_subscribe.call_count == call_count


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt_with_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning after removal."""
    config = copy.deepcopy(DEFAULT_CONFIG_DEVICE)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Remove the tag scanner
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", "")
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    # Rediscover the tag scanner
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt_without_device(
    hass, device_reg, mqtt_mock, tag_mock
):
    """Test tag scanning not firing after removal."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)

    # Remove the tag scanner
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", "")
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()

    # Rediscover the tag scanner
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, None)


async def test_not_fires_on_mqtt_message_after_remove_from_registry(
    hass,
    device_reg,
    mqtt_mock,
    tag_mock,
):
    """Test tag scanning after removal."""
    config = copy.deepcopy(DEFAULT_CONFIG_DEVICE)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    # Fake tag scan.
    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)

    # Remove the device
    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()
    tag_mock.reset_mock()

    async_fire_mqtt_message(hass, "foobar/tag_scanned", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_not_called()


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT device registry integration."""
    registry = dr.async_get(hass)

    data = json.dumps(
        {
            "topic": "test-topic",
            "device": {
                "connections": [["mac", "02:5b:26:a8:dc:12"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(set(), {("mac", "02:5b:26:a8:dc:12")})
    assert device is not None
    assert device.connections == {("mac", "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT device registry integration."""
    registry = dr.async_get(hass)

    data = json.dumps(
        {
            "topic": "test-topic",
            "device": {
                "identifiers": ["helloworld"],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    registry = dr.async_get(hass)

    config = {
        "topic": "test-topic",
        "device": {
            "identifiers": ["helloworld"],
            "connections": [["mac", "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def test_cleanup_tag(hass, device_reg, entity_reg, mqtt_mock):
    """Test tag discovery topic is cleaned when device is removed from registry."""
    config = {
        "topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/tag/bla/config", "", 0, True
    )


async def test_cleanup_device(hass, device_reg, entity_reg, mqtt_mock):
    """Test removal from device registry when tag is removed."""
    config = {
        "topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_several_tags(
    hass, device_reg, entity_reg, mqtt_mock, tag_mock
):
    """Test removal from device registry when the last tag is removed."""
    config1 = {
        "topic": "test-topic1",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "topic": "test-topic2",
        "device": {"identifiers": ["helloworld"]},
    }

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", json.dumps(config1))
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/tag/bla2/config", json.dumps(config2))
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    # Fake tag scan.
    async_fire_mqtt_message(hass, "test-topic1", "12345")
    async_fire_mqtt_message(hass, "test-topic2", "23456")
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, "23456", device_entry.id)

    async_fire_mqtt_message(hass, "homeassistant/tag/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_with_entity_and_trigger_1(
    hass, device_reg, entity_reg, mqtt_mock
):
    """Test removal from device registry for device with tag, entity and trigger.

    Tag removed first, then trigger and entity.
    """
    config1 = {
        "topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config3 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    data3 = json.dumps(config3)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla3/config", data3)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", "")
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla3/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_with_entity2(hass, device_reg, entity_reg, mqtt_mock):
    """Test removal from device registry for device with tag, entity and trigger.

    Trigger and entity removed first, then tag.
    """
    config1 = {
        "topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config3 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    data3 = json.dumps(config3)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla3/config", data3)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", "")
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla3/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    async_fire_mqtt_message(hass, "homeassistant/tag/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None
