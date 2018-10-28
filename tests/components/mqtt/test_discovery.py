"""The tests for the MQTT discovery."""
import asyncio
from unittest.mock import patch

from homeassistant.components import mqtt
from homeassistant.components.mqtt.discovery import async_start, \
                                                    ALREADY_DISCOVERED
from homeassistant.const import STATE_ON, STATE_OFF

from tests.common import async_fire_mqtt_message, mock_coro, MockConfigEntry


@asyncio.coroutine
def test_subscribing_config_topic(hass, mqtt_mock):
    """Test setting up discovery."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={
        mqtt.CONF_BROKER: 'test-broker'
    })

    hass_config = {}
    discovery_topic = 'homeassistant'
    yield from async_start(hass, discovery_topic, hass_config, entry)

    assert mqtt_mock.async_subscribe.called
    call_args = mqtt_mock.async_subscribe.mock_calls[0][1]
    assert call_args[0] == discovery_topic + '/#'
    assert call_args[2] == 0


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_invalid_topic(mock_load_platform, hass, mqtt_mock):
    """Test sending to invalid topic."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={
        mqtt.CONF_BROKER: 'test-broker'
    })

    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {}, entry)

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/not_config',
                            '{}')
    yield from hass.async_block_till_done()
    assert not mock_load_platform.called


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_invalid_json(mock_load_platform, hass, mqtt_mock, caplog):
    """Test sending in invalid JSON."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={
        mqtt.CONF_BROKER: 'test-broker'
    })

    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {}, entry)

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            'not json')
    yield from hass.async_block_till_done()
    assert 'Unable to parse JSON' in caplog.text
    assert not mock_load_platform.called


@patch('homeassistant.components.mqtt.discovery.async_load_platform')
@asyncio.coroutine
def test_only_valid_components(mock_load_platform, hass, mqtt_mock, caplog):
    """Test for a valid component."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    invalid_component = "timer"

    mock_load_platform.return_value = mock_coro()
    yield from async_start(hass, 'homeassistant', {}, entry)

    async_fire_mqtt_message(hass, 'homeassistant/{}/bla/config'.format(
        invalid_component
    ), '{}')

    yield from hass.async_block_till_done()

    assert 'Component {} is not supported'.format(
        invalid_component
    ) in caplog.text

    assert not mock_load_platform.called


@asyncio.coroutine
def test_correct_config_discovery(hass, mqtt_mock, caplog):
    """Test sending in correct JSON."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

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
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            ('{ "name": "Beer",'
                             '  "command_topic": "test_topic" }'))
    yield from hass.async_block_till_done()

    state = hass.states.get('fan.beer')

    assert state is not None
    assert state.name == 'Beer'
    assert ('fan', 'bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_discover_climate(hass, mqtt_mock, caplog):
    """Test discovering an MQTT climate component."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "ClimateTest",'
        '  "current_temperature_topic": "climate/bla/current_temp",'
        '  "temperature_command_topic": "climate/bla/target_temp" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config', data)
    yield from hass.async_block_till_done()

    state = hass.states.get('climate.ClimateTest')

    assert state is not None
    assert state.name == 'ClimateTest'
    assert ('climate', 'bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_discover_alarm_control_panel(hass, mqtt_mock, caplog):
    """Test discovering an MQTT alarm control panel component."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "AlarmControlPanelTest",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data)
    yield from hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.AlarmControlPanelTest')

    assert state is not None
    assert state.name == 'AlarmControlPanelTest'
    assert ('alarm_control_panel', 'bla') in hass.data[ALREADY_DISCOVERED]


@asyncio.coroutine
def test_discovery_incl_nodeid(hass, mqtt_mock, caplog):
    """Test sending in correct JSON with optional node_id included."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

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
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

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


@asyncio.coroutine
def test_discovery_expansion(hass, mqtt_mock, caplog):
    """Test expansion of abbreviated discovery payload."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)

    yield from async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic" }'
    )

    async_fire_mqtt_message(
        hass, 'homeassistant/switch/bla/config', data)
    yield from hass.async_block_till_done()

    state = hass.states.get('switch.DiscoveryExpansionTest1')
    assert state is not None
    assert state.name == 'DiscoveryExpansionTest1'
    assert ('switch', 'bla') in hass.data[ALREADY_DISCOVERED]
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, 'test_topic/some/base/topic',
                            'ON')
    yield from hass.async_block_till_done()
    yield from hass.async_block_till_done()

    state = hass.states.get('switch.DiscoveryExpansionTest1')
    assert state.state == STATE_ON
