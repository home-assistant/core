"""The tests for the Tasmota binary sensor platform."""
import copy
from datetime import timedelta
import json
from unittest.mock import patch

from hatasmota.utils import (
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
)

from homeassistant.components import binary_sensor
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
import homeassistant.util.dt as dt_util

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

from tests.common import async_fire_mqtt_message, async_fire_time_changed


async def test_controlling_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test normal state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"ON"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"OFF"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF

    # Test periodic state update
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", '{"Switch1":"ON"}')
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", '{"Switch1":"OFF"}')
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF

    # Test polled state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/STATUS10", '{"StatusSNS":{"Switch1":"ON"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/STATUS10", '{"StatusSNS":{"Switch1":"OFF"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF

    # Test force update flag
    entity = hass.data["entity_components"]["binary_sensor"].get_entity(
        "binary_sensor.tasmota_binary_sensor_1"
    )
    assert entity.force_update


async def test_controlling_state_via_mqtt_switchname(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Custom Name"
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test normal state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Custom Name":{"Action":"ON"}}'
    )
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_ON

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Custom Name":{"Action":"OFF"}}'
    )
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_OFF

    # Test periodic state update
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", '{"Custom Name":"ON"}')
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", '{"Custom Name":"OFF"}')
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_OFF

    # Test polled state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/STATUS10", '{"StatusSNS":{"Custom Name":"ON"}}'
    )
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_ON

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/STATUS10", '{"StatusSNS":{"Custom Name":"OFF"}}'
    )
    state = hass.states.get("binary_sensor.custom_name")
    assert state.state == STATE_OFF


async def test_pushon_controlling_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 13
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test normal state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"ON"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"OFF"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF

    # Test periodic state update is ignored
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", '{"Switch1":"ON"}')
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF

    # Test polled state update is ignored
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/STATUS10", '{"StatusSNS":{"Switch1":"ON"}}'
    )
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF


async def test_friendly_names(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swc"][1] = 1
    config["swn"][1] = "Beer"
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == "unavailable"
    assert state.attributes.get("friendly_name") == "Tasmota binary_sensor 1"

    state = hass.states.get("binary_sensor.beer")
    assert state.state == "unavailable"
    assert state.attributes.get("friendly_name") == "Beer"


async def test_off_delay(hass, mqtt_mock, setup_tasmota):
    """Test off_delay option."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 13  # PUSHON: 1s off_delay
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    events = []

    @ha.callback
    def callback(event):
        """Verify event got called."""
        events.append(event.data["new_state"].state)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    assert events == ["off"]
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"ON"}}'
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON
    assert events == ["off", "on"]

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"ON"}}'
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_ON
    assert events == ["off", "on", "on"]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.tasmota_binary_sensor_1")
    assert state.state == STATE_OFF
    assert events == ["off", "on", "on", "off"]


async def test_availability_when_connection_lost(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    await help_test_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, binary_sensor.DOMAIN, config
    )


async def test_availability(hass, mqtt_mock, setup_tasmota):
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    await help_test_availability(hass, mqtt_mock, binary_sensor.DOMAIN, config)


async def test_availability_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    await help_test_availability_discovery_update(
        hass, mqtt_mock, binary_sensor.DOMAIN, config
    )


async def test_availability_poll_state(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    poll_topic = "tasmota_49A3BC/cmnd/STATUS"
    await help_test_availability_poll_state(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        binary_sensor.DOMAIN,
        config,
        poll_topic,
        "10",
    )


async def test_discovery_removal_binary_sensor(hass, mqtt_mock, caplog, setup_tasmota):
    """Test removal of discovered binary_sensor."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = 1
    config2["swc"][0] = 0
    config1["swn"][0] = "Test"
    config2["swn"][0] = "Test"

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_binary_sensor(
    hass, mqtt_mock, caplog, setup_tasmota
):
    """Test update of discovered binary_sensor."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    with patch(
        "homeassistant.components.tasmota.binary_sensor.TasmotaBinarySensor.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, binary_sensor.DOMAIN, config, discovery_update
        )


async def test_discovery_device_remove(hass, mqtt_mock, setup_tasmota):
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    unique_id = f"{DEFAULT_CONFIG['mac']}_binary_sensor_switch_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, binary_sensor.DOMAIN, unique_id, config
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock, setup_tasmota):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    topics = [
        get_topic_stat_result(config),
        get_topic_tele_sensor(config),
        get_topic_stat_status(config, 10),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, binary_sensor.DOMAIN, config, topics
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 1
    config["swn"][0] = "Test"
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, binary_sensor.DOMAIN, config
    )
