"""Common test objects."""
import copy
import json

from hatasmota.const import (
    CONF_ID,
    CONF_OFFLINE,
    CONF_ONLINE,
    CONF_PREFIX,
    PREFIX_CMND,
    PREFIX_TELE,
)
from hatasmota.utils import (
    get_state_offline,
    get_state_online,
    get_topic_tele_state,
    get_topic_tele_will,
)

from homeassistant.components.mqtt.const import MQTT_DISCONNECTED
from homeassistant.components.tasmota import DEFAULT_PREFIX
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_tasmota

from tests.async_mock import ANY, patch
from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG_DEVICE_INFO_ID = {
    "identifiers": ["helloworld"],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "sw_version": "0.1-beta",
}

DEFAULT_CONFIG_DEVICE_INFO_MAC = {
    "connections": [["mac", "02:5b:26:a8:dc:12"]],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "sw_version": "0.1-beta",
}


async def help_test_availability_when_connection_lost(hass, mqtt_mock, domain, config):
    """Test availability after MQTT disconnection."""
    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        get_state_online(config),
    )

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE


async def help_test_availability(
    hass,
    mqtt_mock,
    domain,
    config,
):
    """Test availability.

    This is a test helper for the TasmotaAvailability mixin.
    """
    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        get_state_online(config),
    )

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        get_state_offline(config),
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
    offline1 = get_state_offline(config1)
    offline2 = get_state_offline(config2)
    assert offline1 != offline2
    online1 = get_state_online(config1)
    online2 = get_state_online(config2)
    assert online1 != online2

    await setup_tasmota(hass)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config1[CONF_ID]}/config", data1)
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
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config2[CONF_ID]}/config", data2)
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
    assert config1[CONF_ID] == config2[CONF_ID]

    await setup_tasmota(hass)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config1[CONF_ID]}/config", data1)
    await hass.async_block_till_done()

    # Verify device and entity registry entries are created
    device_entry = device_reg.async_get_device({("tasmota", config1[CONF_ID])}, set())
    assert device_entry is not None
    entity_entry = entity_reg.async_get(f"{domain}.test")
    assert entity_entry is not None

    # Verify state is added
    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "Test"

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config2[CONF_ID]}/config", data2)
    await hass.async_block_till_done()

    # Verify entity registry entries are cleared
    device_entry = device_reg.async_get_device({("tasmota", config2[CONF_ID])}, set())
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

    await setup_tasmota(hass)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "Test"

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data1)
    await hass.async_block_till_done()

    assert not discovery_update.called

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data2)
    await hass.async_block_till_done()

    assert discovery_update.called


async def help_test_discovery_broken(hass, mqtt_mock, caplog, domain, config):
    """Test handling of exception when creating discovered entity."""
    data = json.dumps(config)

    await setup_tasmota(hass)

    # Trigger an exception when the entity is added
    with patch(
        "hatasmota.discovery.get_switch_entities",
        return_value=[object()],
    ):
        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data
        )
        await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None

    # Make sure the entity is added, instead of a discovery update
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "Test"


async def help_test_discovery_device_remove(hass, mqtt_mock, domain, config):
    """Test domain entity is removed when device is removed."""
    device_reg = await hass.helpers.device_registry.async_get_registry()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(config)
    unique_id = f"{config[CONF_ID]}_{domain}_0"

    await setup_tasmota(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data)
    await hass.async_block_till_done()

    device = device_reg.async_get_device({("tasmota", config[CONF_ID])}, set())
    assert device is not None
    assert entity_reg.async_get_entity_id(domain, "tasmota", unique_id)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", "")
    await hass.async_block_till_done()

    device = device_reg.async_get_device({("tasmota", config[CONF_ID])}, set())
    assert device is None
    assert not entity_reg.async_get_entity_id(domain, "tasmota", unique_id)


async def help_test_entity_id_update_subscriptions(
    hass, mqtt_mock, domain, config, topics=None
):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(config)
    data = json.dumps(config)

    await setup_tasmota(hass)
    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data)
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

    await setup_tasmota(hass)

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, get_state_online(config))
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, topic, get_state_offline(config))
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    entity_reg.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()

    assert config[CONF_PREFIX][PREFIX_TELE] != "tele2"
    config[CONF_PREFIX][PREFIX_TELE] = "tele2"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_ID]}/config", data)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1

    topic = get_topic_tele_will(config)
    async_fire_mqtt_message(hass, topic, get_state_online(config))
    state = hass.states.get(f"{domain}.milk")
    assert state.state != STATE_UNAVAILABLE
