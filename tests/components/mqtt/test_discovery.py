"""The tests for the MQTT discovery."""
import asyncio
from unittest.mock import patch

from homeassistant.components.mqtt.discovery import async_start, \
                                                    ALREADY_DISCOVERED

from tests.common import async_fire_mqtt_message, mock_coro


@asyncio.coroutine
def test_subscribing_config_topic(hass, mqtt_mock):
    """Test setting up discovery."""
    hass_config = {}
    discovery_topic = 'homeassistant'
    yield from async_start(hass, discovery_topic, hass_config)

    assert mqtt_mock.async_subscribe.called
    call_args = mqtt_mock.async_subscribe.mock_calls[0][1]
    assert call_args[0] == discovery_topic + '/#'
    assert call_args[2] == 0


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_invalid_topic(mock_load_platform, hass, mqtt_mock):
    """Test sending to invalid topic."""
    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/not_config',
                            '{}')
    yield from hass.async_block_till_done()
    assert not mock_load_platform.called


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_invalid_json(mock_load_platform, hass, mqtt_mock, caplog):
    """Test sending in invalid JSON."""
    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            'not json')
    yield from hass.async_block_till_done()
    assert 'Unable to parse JSON' in caplog.text
    assert not mock_load_platform.called


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_only_valid_components(mock_load_platform, hass, mqtt_mock, caplog):
    """Test for a valid component."""
    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config', '{}')
    yield from hass.async_block_till_done()
    assert 'Component climate is not supported' in caplog.text
    assert not mock_load_platform.called


@asyncio.coroutine
def test_correct_config_discovery(hass, mqtt_mock, caplog):
    """Test sending in correct JSON."""
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            '{ "name": "Beer" }')
    yield from hass.async_block_till_done()

    state = hass.states.get('binary_sensor.beer')

    assert state is not None
    assert state.name == 'Beer'
    assert ('binary_sensor', 'bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_discover_fan(hass, mqtt_mock, caplog):
    """Test discovering an MQTT fan."""
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            ('{ "name": "Beer",'
                             '  "command_topic": "test_topic" }'))
    yield from hass.async_block_till_done()

    state = hass.states.get('fan.beer')

    assert state is not None
    assert state.name == 'Beer'
    assert ('fan', 'bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_discovery_incl_nodeid(hass, mqtt_mock, caplog):
    """Test sending in correct JSON with optional node_id included."""
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/my_node_id/bla'
                            '/config', '{ "name": "Beer" }')
    yield from hass.async_block_till_done()

    state = hass.states.get('binary_sensor.beer')

    assert state is not None
    assert state.name == 'Beer'
    assert ('binary_sensor', 'my_node_id_bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_non_duplicate_discovery(hass, mqtt_mock, caplog):
    """Test for a non duplicate component."""
    yield from async_start(hass, 'homeassistant', {})

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            '{ "name": "Beer" }')
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            '{ "name": "Beer" }')
    yield from hass.async_block_till_done()

    state = hass.states.get('binary_sensor.beer')
    state_duplicate = hass.states.get('binary_sensor.beer1')

    assert state is not None
    assert state.name == 'Beer'
    assert state_duplicate is None
    assert 'Component has already been discovered: ' \
           'binary_sensor bla' in caplog.text
