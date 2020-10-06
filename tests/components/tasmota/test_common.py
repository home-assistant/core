"""Common test objects."""
import copy
import json

from hatasmota.const import (
    CONF_MAC,
    CONF_OFFLINE,
    CONF_ONLINE,
    CONF_PREFIX,
    PREFIX_CMND,
    PREFIX_TELE,
)
from hatasmota.utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_tele_state,
    get_topic_tele_will,
)

from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import STATE_UNAVAILABLE

from tests.async_mock import ANY
from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    "ip": "192.168.15.10",
    "dn": "Tasmota",
    "fn": ["Test", "Beer", "Milk", "Four", None],
    "hn": "tasmota_49A3BC-0956",
    "lk": 1,  # RGB + white channels linked to a single light
    "mac": "00000049A3BC",
    "md": "Sonoff Basic",
    "ofln": "Offline",
    "onln": "Online",
    "state": ["OFF", "ON", "TOGGLE", "HOLD"],
    "sw": "8.4.0.2",
    "t": "tasmota_49A3BC",
    "ft": "%topic%/%prefix%/",
    "tp": ["cmnd", "stat", "tele"],
    "rl": [0, 0, 0, 0, 0, 0, 0, 0],
    "swc": [-1, -1, -1, -1, -1, -1, -1, -1],
    "btn": [0, 0, 0, 0],
    "so": {
        "11": 0,  # Swap button single and double press functionality
        "13": 0,  # Allow immediate action on single button press
        "17": 1,  # Show Color string as hex or comma-separated
        "20": 0,  # Update of Dimmer/Color/CT without turning power on
        "30": 0,  # Enforce Home Assistant auto-discovery as light
        "68": 0,  # Multi-channel PWM instead of a single light
        "73": 0,  # Enable Buttons decoupling and send multi-press and hold MQTT messages
        "80": 0,  # Blinds and shutters support
    },
    "lt_st": 0,
    "ver": 1,
}


async def help_test_availability_when_connection_lost(
    hass, mqtt_client_mock, mqtt_mock, domain, config
):
    """Test availability after MQTT disconnection."""
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        config_get_state_online(config),
    )

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    mqtt_mock.connected = False
    await hass.async_add_executor_job(mqtt_client_mock.on_disconnect, None, None, 0)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    mqtt_mock.connected = True
    await hass.async_add_executor_job(mqtt_client_mock.on_connect, None, None, None, 0)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE


async def help_test_availability(
    hass,
    mqtt_mock,
    domain,
    config,
):
    """Test availability.

    This is a test helper for the TasmotaAvailability mixin.
    """
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        config_get_state_online(config),
    )

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        config_get_state_offline(config),
    )

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE


async def help_test_availability_discovery_update(
    hass,
    mqtt_mock,
    domain,
    config,
):
    """Test update of discovered TasmotaAvailability.

    This is a test helper for the TasmotaAvailability mixin.
    """
    # customize availability topic
    config1 = copy.deepcopy(config)
    config1[CONF_PREFIX][PREFIX_TELE] = "tele1"
    config1[CONF_OFFLINE] = "offline1"
    config1[CONF_ONLINE] = "online1"
    config2 = copy.deepcopy(config)
    config2[CONF_PREFIX][PREFIX_TELE] = "tele2"
    config2[CONF_OFFLINE] = "offline2"
    config2[CONF_ONLINE] = "online2"
    data1 = json.dumps(config1)
    data2 = json.dumps(config2)

    availability_topic1 = get_topic_tele_will(config1)
    availability_topic2 = get_topic_tele_will(config2)
    assert availability_topic1 != availability_topic2
    offline1 = config_get_state_offline(config1)
    offline2 = config_get_state_offline(config2)
    assert offline1 != offline2
    online1 = config_get_state_online(config1)
    online2 = config_get_state_online(config2)
    assert online1 != online2

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config1[CONF_MAC]}/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, availability_topic1, online1)
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, availability_topic1, offline1)
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Change availability settings
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config2[CONF_MAC]}/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic or payload
    async_fire_mqtt_message(hass, availability_topic1, online1)
    async_fire_mqtt_message(hass, availability_topic1, online2)
    async_fire_mqtt_message(hass, availability_topic2, online1)
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, availability_topic2, online2)
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE


async def help_test_discovery_removal(
    hass, mqtt_mock, caplog, domain, config1, config2
):
    """Test removal of discovered entity."""
    device_reg = await hass.helpers.device_registry.async_get_registry()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    assert config1[CONF_MAC] == config2[CONF_MAC]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config1[CONF_MAC]}/config", data1)
    await hass.async_block_till_done()

    # Verify device and entity registry entries are created
    device_entry = device_reg.async_get_device(set(), {("mac", config1[CONF_MAC])})
    assert device_entry is not None
    entity_entry = entity_reg.async_get(f"{domain}.test")
    assert entity_entry is not None

    # Verify state is added
    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "Test"

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config2[CONF_MAC]}/config", data2)
    await hass.async_block_till_done()

    # Verify entity registry entries are cleared
    device_entry = device_reg.async_get_device(set(), {("mac", config2[CONF_MAC])})
    assert device_entry is not None
    entity_entry = entity_reg.async_get(f"{domain}.test")
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get(f"{domain}.test")
    assert state is None


async def help_test_discovery_update_unchanged(
    hass, mqtt_mock, caplog, domain, config, discovery_update
):
    """Test update of discovered component without changes.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    config1 = copy.deepcopy(config)
    config2 = copy.deepcopy(config)
    config2[CONF_PREFIX][PREFIX_CMND] = "cmnd2"
    data1 = json.dumps(config1)
    data2 = json.dumps(config2)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "Test"

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data1)
    await hass.async_block_till_done()

    assert not discovery_update.called

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data2)
    await hass.async_block_till_done()

    assert discovery_update.called


async def help_test_discovery_device_remove(hass, mqtt_mock, domain, unique_id, config):
    """Test domain entity is removed when device is removed."""
    device_reg = await hass.helpers.device_registry.async_get_registry()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(config)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data)
    await hass.async_block_till_done()

    device = device_reg.async_get_device(set(), {("mac", config[CONF_MAC])})
    assert device is not None
    assert entity_reg.async_get_entity_id(domain, "tasmota", unique_id)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", "")
    await hass.async_block_till_done()

    device = device_reg.async_get_device(set(), {("mac", config[CONF_MAC])})
    assert device is None
    assert not entity_reg.async_get_entity_id(domain, "tasmota", unique_id)


async def help_test_entity_id_update_subscriptions(
    hass, mqtt_mock, domain, config, topics=None
):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(config)
    data = json.dumps(config)

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data)
    await hass.async_block_till_done()

    topics = [get_topic_tele_state(config), get_topic_tele_will(config)]
    assert len(topics) > 0

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert mqtt_mock.async_subscribe.call_count == len(topics)
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, ANY, ANY)
    mqtt_mock.async_subscribe.reset_mock()

    entity_reg.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, ANY, ANY)


async def help_test_entity_id_update_discovery_update(hass, mqtt_mock, domain, config):
    """Test MQTT discovery update after entity_id is updated."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(config)
    data = json.dumps(config)

    topic = get_topic_tele_will(config)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, config_get_state_online(config))
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, topic, config_get_state_offline(config))
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    entity_reg.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()
    assert hass.states.get(f"{domain}.milk")

    assert config[CONF_PREFIX][PREFIX_TELE] != "tele2"
    config[CONF_PREFIX][PREFIX_TELE] = "tele2"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1

    topic = get_topic_tele_will(config)
    async_fire_mqtt_message(hass, topic, config_get_state_online(config))
    state = hass.states.get(f"{domain}.milk")
    assert state.state != STATE_UNAVAILABLE
