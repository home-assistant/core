"""The tests for the  MQTT device_tracker discovery platform."""

import pytest

from homeassistant.components.mqtt.discovery import ALREADY_DISCOVERED
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNKNOWN

from tests.common import async_fire_mqtt_message, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_discover_device_tracker(hass, mqtt_mock, caplog):
    """Test discovering an MQTT device tracker component."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "state_topic": "test_topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")

    assert state is not None
    assert state.name == "test"
    assert ("device_tracker", "bla") in hass.data[ALREADY_DISCOVERED]


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is None

    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "required-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Beer"


async def test_non_duplicate_device_tracker_discovery(hass, mqtt_mock, caplog):
    """Test for a non duplicate component."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    state_duplicate = hass.states.get("device_tracker.beer1")

    assert state is not None
    assert state.name == "Beer"
    assert state_duplicate is None
    assert "Component has already been discovered: device_tracker bla" in caplog.text


async def test_device_tracker_removal(hass, mqtt_mock, caplog):
    """Test removal of component through empty discovery message."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.beer")
    assert state is not None

    async_fire_mqtt_message(hass, "homeassistant/device_tracker/bla/config", "")
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.beer")
    assert state is None


async def test_device_tracker_rediscover(hass, mqtt_mock, caplog):
    """Test rediscover of removed component."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.beer")
    assert state is not None

    async_fire_mqtt_message(hass, "homeassistant/device_tracker/bla/config", "")
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.beer")
    assert state is None

    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.beer")
    assert state is not None


async def test_duplicate_device_tracker_removal(hass, mqtt_mock, caplog):
    """Test for a non duplicate component."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/device_tracker/bla/config", "")
    await hass.async_block_till_done()
    assert "Component has already been discovered: device_tracker bla" in caplog.text
    caplog.clear()
    async_fire_mqtt_message(hass, "homeassistant/device_tracker/bla/config", "")
    await hass.async_block_till_done()

    assert (
        "Component has already been discovered: device_tracker bla" not in caplog.text
    )


async def test_device_tracker_discovery_update(hass, mqtt_mock, caplog):
    """Test for a discovery update event."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Cider", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Cider"


async def test_cleanup_device_tracker(hass, device_reg, entity_reg, mqtt_mock):
    """Test discvered device is cleaned up when removed from registry."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/tracker",'
        '  "unique_id": "unique" }',
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is not None
    entity_entry = entity_reg.async_get("device_tracker.mqtt_unique")
    assert entity_entry is not None

    state = hass.states.get("device_tracker.mqtt_unique")
    assert state is not None

    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    # Verify device and registry entries are cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is None
    entity_entry = entity_reg.async_get("device_tracker.mqtt_unique")
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("device_tracker.mqtt_unique")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/device_tracker/bla/config", "", 0, True
    )


async def test_setting_device_tracker_value_via_mqtt_message(hass, mqtt_mock, caplog):
    """Test the setting of the value via MQTT."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "state_topic": "test-topic" }',
    )

    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")

    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "home")
    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_HOME

    async_fire_mqtt_message(hass, "test-topic", "not_home")
    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_NOT_HOME


async def test_setting_device_tracker_value_via_mqtt_message_and_template(
    hass, mqtt_mock, caplog
):
    """Test the setting of the value via MQTT."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        "{"
        '"name": "test", '
        '"state_topic": "test-topic", '
        '"value_template": "{% if value is equalto \\"proxy_for_home\\" %}home{% else %}not_home{% endif %}" '
        "}",
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "proxy_for_home")
    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_HOME

    async_fire_mqtt_message(hass, "test-topic", "anything_for_not_home")
    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_NOT_HOME


async def test_setting_device_tracker_value_via_mqtt_message_and_template2(
    hass, mqtt_mock, caplog
):
    """Test the setting of the value via MQTT."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        "{"
        '"name": "test", '
        '"state_topic": "test-topic", '
        '"value_template": "{{ value | lower }}" '
        "}",
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "HOME")
    state = hass.states.get("device_Tracker.test")
    assert state.state == STATE_HOME

    async_fire_mqtt_message(hass, "test-topic", "NOT_HOME")
    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_NOT_HOME


async def test_setting_device_tracker_location_via_mqtt_message(
    hass, mqtt_mock, caplog
):
    """Test the setting of the location via MQTT."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")

    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "test-location")
    state = hass.states.get("device_tracker.test")
    assert state.state == "test-location"


async def test_setting_device_tracker_location_via_lat_lon_message(
    hass, mqtt_mock, caplog
):
    """Test the setting of the latitude and longitude via MQTT."""
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        "{ "
        '"name": "test", '
        '"state_topic": "test-topic", '
        '"json_attributes_topic": "attributes-topic" '
        "}",
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")

    assert state.state == STATE_UNKNOWN

    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":32.87336,"longitude": -117.22743, "gps_accuracy":1.5}',
    )
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.attributes["longitude"] == -117.22743
    assert state.attributes["gps_accuracy"] == 1.5
    assert state.state == STATE_HOME

    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":50.1,"longitude": -2.1, "gps_accuracy":1.5}',
    )
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 50.1
    assert state.attributes["longitude"] == -2.1
    assert state.attributes["gps_accuracy"] == 1.5
    assert state.state == STATE_NOT_HOME

    async_fire_mqtt_message(hass, "attributes-topic", '{"longitude": -117.22743}')
    state = hass.states.get("device_tracker.test")
    assert state.attributes["longitude"] == -117.22743
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "attributes-topic", '{"latitude":32.87336}')
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.state == STATE_NOT_HOME
