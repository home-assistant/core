"""The tests for the  MQTT binary sensor platform."""
from datetime import timedelta
import json
import unittest
from unittest.mock import ANY, Mock

from homeassistant.components import binary_sensor, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_OFF, STATE_ON, STATE_UNAVAILABLE)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    fire_mqtt_message, fire_time_changed, get_test_home_assistant,
    mock_component, mock_mqtt_component, mock_registry)


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config_entries._async_schedule_save = Mock()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        """Test the setting of the value via MQTT."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_OFF == state.state

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_ON == state.state

        fire_mqtt_message(self.hass, 'test-topic', 'OFF')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_OFF == state.state

    def test_setting_sensor_value_via_mqtt_message_and_template(self):
        """Test the setting of the value via MQTT."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
                'value_template': '{%if is_state(entity_id,\"on\")-%}OFF'
                                  '{%-else-%}ON{%-endif%}'
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_OFF == state.state

        fire_mqtt_message(self.hass, 'test-topic', '')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_ON == state.state

        fire_mqtt_message(self.hass, 'test-topic', '')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_OFF == state.state

    def test_valid_device_class(self):
        """Test the setting of a valid sensor class."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'device_class': 'motion',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert 'motion' == state.attributes.get('device_class')

    def test_invalid_device_class(self):
        """Test the setting of an invalid sensor class."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'device_class': 'abc123',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert state is None

    def test_availability_without_topic(self):
        """Test availability without defined availability topic."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE != state.state

    def test_availability_by_defaults(self):
        """Test availability by defaults with defined topic."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'availability_topic': 'availability-topic'
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE == state.state

    def test_availability_by_custom_payload(self):
        """Test availability by custom payload with defined topic."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert STATE_UNAVAILABLE == state.state

    def test_force_update_disabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF'
            }
        })

        events = []

        @ha.callback
        def callback(event):
            """Verify event got called."""
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        assert 1 == len(events)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        assert 1 == len(events)

    def test_force_update_enabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
                'force_update': True
            }
        })

        events = []

        @ha.callback
        def callback(event):
            """Verify event got called."""
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        assert 1 == len(events)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        assert 2 == len(events)

    def test_off_delay(self):
        """Test off_delay option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
                'off_delay': 30,
                'force_update': True
            }
        })

        events = []

        @ha.callback
        def callback(event):
            """Verify event got called."""
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_ON == state.state
        assert 1 == len(events)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_ON == state.state
        assert 2 == len(events)

        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=30))
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        assert STATE_OFF == state.state
        assert 3 == len(events)


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.test')

    assert '100' == state.attributes.get('val')


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.attributes.get('val') is None
    assert 'Erroneous JSON: This is not JSON' in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert '100' == state.attributes.get('val')

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert '100' == state.attributes.get('val')

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert '75' == state.attributes.get('val')


async def test_unique_id(hass):
    """Test unique id option only creates one sensor per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'state_topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'state_topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })
    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1


async def test_discovery_removal_binary_sensor(hass, mqtt_mock, caplog):
    """Test removal of discovered binary_sensor."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "availability_topic": "availability_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert state is None


async def test_discovery_update_binary_sensor(hass, mqtt_mock, caplog):
    """Test update of discovered binary_sensor."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "availability_topic": "availability_topic1" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic2",'
        '  "availability_topic": "availability_topic2" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data1)
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.beer')
    assert state is not None
    assert state.name == 'Milk'

    state = hass.states.get('binary_sensor.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "off_delay": -1 }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('binary_sensor.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT binary sensor device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    })
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/binary_sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'state_topic': 'test-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('binary_sensor.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity(
        'binary_sensor.beer', new_entity_id='binary_sensor.milk')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.beer')
    assert state is None

    state = hass.states.get('binary_sensor.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
