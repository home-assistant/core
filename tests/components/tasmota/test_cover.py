"""The tests for the Tasmota cover platform."""
import copy
import json
from unittest.mock import patch

from hatasmota.utils import (
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
)

from homeassistant.components import cover
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNKNOWN

from .test_common import (
    DEFAULT_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
)

from tests.common import async_fire_mqtt_message


async def test_missing_relay(hass, mqtt_mock, setup_tasmota):
    """Test no cover is discovered if relays are missing."""


async def test_controlling_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 3
    config["rl"][1] = 3
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == STATE_UNKNOWN
    assert (
        state.attributes["supported_features"]
        == cover.SUPPORT_OPEN
        | cover.SUPPORT_CLOSE
        | cover.SUPPORT_STOP
        | cover.SUPPORT_SET_POSITION
    )
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Periodic updates
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":54,"Direction":-1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 54

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":100,"Direction":1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"Shutter1":{"Position":0,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"Shutter1":{"Position":1,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 1

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":100,"Direction":0}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100

    # State poll response
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":54,"Direction":-1}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 54

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":100,"Direction":1}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":0,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":1,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 1

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":100,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100

    # Command response
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":54,"Direction":-1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 54

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":100,"Direction":1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Shutter1":{"Position":0,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Shutter1":{"Position":1,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 1

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":100,"Direction":0}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100


async def test_controlling_state_via_mqtt_inverted(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 3
    config["rl"][1] = 3
    config["sho"] = [1]  # Inverted cover
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == STATE_UNKNOWN
    assert (
        state.attributes["supported_features"]
        == cover.SUPPORT_OPEN
        | cover.SUPPORT_CLOSE
        | cover.SUPPORT_STOP
        | cover.SUPPORT_SET_POSITION
    )
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Periodic updates
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":54,"Direction":-1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 46

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":100,"Direction":1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"Shutter1":{"Position":0,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"Shutter1":{"Position":99,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 1

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/SENSOR",
        '{"Shutter1":{"Position":100,"Direction":0}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0

    # State poll response
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":54,"Direction":-1}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 46

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":100,"Direction":1}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":0,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":99,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 1

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"Shutter1":{"Position":100,"Direction":0}}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0

    # Command response
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":54,"Direction":-1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "opening"
    assert state.attributes["current_position"] == 46

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":100,"Direction":1}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closing"
    assert state.attributes["current_position"] == 0

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Shutter1":{"Position":0,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 100

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Shutter1":{"Position":1,"Direction":0}}'
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "open"
    assert state.attributes["current_position"] == 99

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/RESULT",
        '{"Shutter1":{"Position":100,"Direction":0}}',
    )
    state = hass.states.get("cover.tasmota_cover_1")
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0


async def call_service(hass, entity_id, service, **kwargs):
    """Call a fan service."""
    await hass.services.async_call(
        cover.DOMAIN,
        service,
        {"entity_id": entity_id, **kwargs},
        blocking=True,
    )


async def test_sending_mqtt_commands(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("cover.test_cover_1")
    assert state.state == STATE_UNKNOWN
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Close the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "close_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterClose1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be unknown
    state = hass.states.get("cover.test_cover_1")
    assert state.state == STATE_UNKNOWN

    # Open the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "open_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterOpen1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Stop the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "stop_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterStop1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set position and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "set_cover_position", position=0)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterPosition1", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set position and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "set_cover_position", position=99)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterPosition1", "99", 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_sending_mqtt_commands_inverted(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    config["sho"] = [1]  # Inverted cover
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("cover.test_cover_1")
    assert state.state == STATE_UNKNOWN
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Close the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "close_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterClose1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be unknown
    state = hass.states.get("cover.test_cover_1")
    assert state.state == STATE_UNKNOWN

    # Open the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "open_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterOpen1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Stop the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "stop_cover")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterStop1", "", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set position and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "set_cover_position", position=0)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterPosition1", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set position and verify MQTT message is sent
    await call_service(hass, "cover.test_cover_1", "set_cover_position", position=99)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/ShutterPosition1", "1", 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_availability_when_connection_lost(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    await help_test_availability_when_connection_lost(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        cover.DOMAIN,
        config,
        entity_id="test_cover_1",
    )


async def test_availability(hass, mqtt_mock, setup_tasmota):
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    await help_test_availability(
        hass, mqtt_mock, cover.DOMAIN, config, entity_id="test_cover_1"
    )


async def test_availability_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    await help_test_availability_discovery_update(
        hass, mqtt_mock, cover.DOMAIN, config, entity_id="test_cover_1"
    )


async def test_availability_poll_state(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 3
    config["rl"][1] = 3
    poll_topic = "tasmota_49A3BC/cmnd/STATUS"
    await help_test_availability_poll_state(
        hass, mqtt_client_mock, mqtt_mock, cover.DOMAIN, config, poll_topic, "10"
    )


async def test_discovery_removal_cover(hass, mqtt_mock, caplog, setup_tasmota):
    """Test removal of discovered cover."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["dn"] = "Test"
    config1["rl"][0] = 3
    config1["rl"][1] = 3
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["dn"] = "Test"
    config2["rl"][0] = 0
    config2["rl"][1] = 0

    await help_test_discovery_removal(
        hass,
        mqtt_mock,
        caplog,
        cover.DOMAIN,
        config1,
        config2,
        entity_id="test_cover_1",
        name="Test cover 1",
    )


async def test_discovery_update_unchanged_cover(hass, mqtt_mock, caplog, setup_tasmota):
    """Test update of discovered cover."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    with patch(
        "homeassistant.components.tasmota.cover.TasmotaCover.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock,
            caplog,
            cover.DOMAIN,
            config,
            discovery_update,
            entity_id="test_cover_1",
            name="Test cover 1",
        )


async def test_discovery_device_remove(hass, mqtt_mock, setup_tasmota):
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    unique_id = f"{DEFAULT_CONFIG['mac']}_cover_shutter_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, cover.DOMAIN, unique_id, config
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock, setup_tasmota):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    topics = [
        get_topic_stat_result(config),
        get_topic_tele_sensor(config),
        get_topic_stat_status(config, 10),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, cover.DOMAIN, config, topics, entity_id="test_cover_1"
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["rl"][0] = 3
    config["rl"][1] = 3
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, cover.DOMAIN, config, entity_id="test_cover_1"
    )
