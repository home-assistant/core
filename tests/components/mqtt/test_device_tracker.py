"""The tests for the MQTT device_tracker platform."""
from datetime import UTC, datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import device_tracker, mqtt
from homeassistant.components.mqtt.const import DOMAIN as MQTT_DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_reloadable,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
)

from tests.common import async_fire_mqtt_message
from tests.typing import (
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    WebSocketGenerator,
)

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        device_tracker.DOMAIN: {
            "name": "test",
            "state_topic": "test-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def device_tracker_platform_only():
    """Only setup the device_tracker platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.DEVICE_TRACKER]):
        yield


async def test_discover_device_tracker(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test discovering an MQTT device tracker component."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "state_topic": "test_topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")

    assert state is not None
    assert state.name == "test"
    assert ("device_tracker", "bla") in hass.data["mqtt"].discovery_already_discovered


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    await mqtt_mock_entry()
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


async def test_non_duplicate_device_tracker_discovery(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for a non duplicate component."""
    await mqtt_mock_entry()
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


async def test_device_tracker_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of component through empty discovery message."""
    await mqtt_mock_entry()
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


async def test_device_tracker_rediscover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test rediscover of removed component."""
    await mqtt_mock_entry()
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


async def test_duplicate_device_tracker_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for a non duplicate component."""
    await mqtt_mock_entry()
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


async def test_device_tracker_discovery_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for a discovery update event."""
    freezer.move_to("2023-08-22 19:15:00+00:00")
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Beer"
    assert state.last_updated == datetime(2023, 8, 22, 19, 15, tzinfo=UTC)

    freezer.move_to("2023-08-22 19:16:00+00:00")
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Cider", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Cider"
    assert state.last_updated == datetime(2023, 8, 22, 19, 16, tzinfo=UTC)

    freezer.move_to("2023-08-22 19:20:00+00:00")
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "Cider", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.beer")
    assert state is not None
    assert state.name == "Cider"
    # Entity was not updated as the state was not changed
    assert state.last_updated == datetime(2023, 8, 22, 19, 16, tzinfo=UTC)


async def test_cleanup_device_tracker(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discovered device is cleaned up when removed from registry."""
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()
    ws_client = await hass_ws_client(hass)

    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/tracker",'
        '  "unique_id": "unique" }',
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    entity_entry = entity_registry.async_get("device_tracker.mqtt_unique")
    assert entity_entry is not None

    state = hass.states.get("device_tracker.mqtt_unique")
    assert state is not None

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(MQTT_DOMAIN)[0]
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

    # Verify device and registry entries are cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None
    entity_entry = entity_registry.async_get("device_tracker.mqtt_unique")
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("device_tracker.mqtt_unique")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/device_tracker/bla/config", "", 0, True
    )


async def test_setting_device_tracker_value_via_mqtt_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the value via MQTT."""
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the value via MQTT."""
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the value via MQTT."""
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the location via MQTT."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "state_topic": "test-topic", "source_type": "router" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")
    assert state.attributes["source_type"] == "router"

    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "test-location")
    state = hass.states.get("device_tracker.test")
    assert state.state == "test-location"


async def test_setting_device_tracker_location_via_lat_lon_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the latitude and longitude via MQTT without state topic."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        '{ "name": "test", "json_attributes_topic": "attributes-topic"}',
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")
    assert state.attributes["source_type"] == "gps"

    assert state.state == STATE_UNKNOWN

    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":32.87336,"longitude": -117.22743, "gps_accuracy":1.5, "source_type": "router"}',
    )
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.attributes["longitude"] == -117.22743
    assert state.attributes["gps_accuracy"] == 1.5
    # assert source_type is overridden by discovery
    assert state.attributes["source_type"] == "router"
    assert state.state == STATE_HOME

    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":50.1,"longitude": -2.1}',
    )
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 50.1
    assert state.attributes["longitude"] == -2.1
    assert state.attributes["gps_accuracy"] == 0
    assert state.state == STATE_NOT_HOME

    async_fire_mqtt_message(hass, "attributes-topic", '{"longitude": -117.22743}')
    state = hass.states.get("device_tracker.test")
    assert state.attributes["longitude"] == -117.22743
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "attributes-topic", '{"latitude":32.87336}')
    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.state == STATE_UNKNOWN


async def test_setting_device_tracker_location_via_reset_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the automatic inference of zones via MQTT via reset."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        "{ "
        '"name": "test", '
        '"state_topic": "test-topic", '
        '"json_attributes_topic": "attributes-topic" '
        "}",
    )

    hass.states.async_set(
        "zone.school",
        "zoning",
        {
            "latitude": 30.0,
            "longitude": -100.0,
            "radius": 100,
            "friendly_name": "School",
        },
    )

    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")
    assert state.attributes["source_type"] == "gps"

    assert state.state == STATE_UNKNOWN

    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

    # test reset and gps attributes
    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":32.87336,"longitude": -117.22743, "gps_accuracy":1.5}',
    )
    async_fire_mqtt_message(hass, "test-topic", "None")

    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.attributes["longitude"] == -117.22743
    assert state.attributes["gps_accuracy"] == 1.5
    assert state.attributes["source_type"] == "gps"
    assert state.state == STATE_HOME

    # test manual state override
    async_fire_mqtt_message(hass, "test-topic", "Work")

    state = hass.states.get("device_tracker.test")
    assert state.state == "Work"

    # test reset
    async_fire_mqtt_message(hass, "test-topic", "None")

    state = hass.states.get("device_tracker.test")
    assert state.state == STATE_HOME

    # test reset inferring correct school area
    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":30.0,"longitude":-100.0,"gps_accuracy":1.5}',
    )

    state = hass.states.get("device_tracker.test")
    assert state.state == "School"


async def test_setting_device_tracker_location_via_abbr_reset_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of reset via abbreviated names and custom payloads via MQTT."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device_tracker/bla/config",
        "{ "
        '"name": "test", '
        '"state_topic": "test-topic", '
        '"json_attributes_topic": "attributes-topic", '
        '"pl_rst": "reset" '
        "}",
    )

    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test")
    assert state.attributes["source_type"] == "gps"

    assert state.state == STATE_UNKNOWN

    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

    # test custom reset payload and gps attributes
    async_fire_mqtt_message(
        hass,
        "attributes-topic",
        '{"latitude":32.87336,"longitude": -117.22743, "gps_accuracy":1.5}',
    )
    async_fire_mqtt_message(hass, "test-topic", "reset")

    state = hass.states.get("device_tracker.test")
    assert state.attributes["latitude"] == 32.87336
    assert state.attributes["longitude"] == -117.22743
    assert state.attributes["gps_accuracy"] == 1.5
    assert state.attributes["source_type"] == "gps"
    assert state.state == STATE_HOME


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        device_tracker.DOMAIN,
        DEFAULT_CONFIG,
        None,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                device_tracker.DOMAIN: {"name": "jan", "state_topic": "/location/jan"}
            }
        }
    ],
)
async def test_setup_with_modern_schema(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup using the modern schema."""
    await mqtt_mock_entry()
    dev_id = "jan"
    entity_id = f"{device_tracker.DOMAIN}.{dev_id}"
    assert hass.states.get(entity_id) is not None


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test reloading the MQTT platform."""
    domain = device_tracker.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)
