"""The tests for the MQTT sensor platform."""
from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import ANY, patch

from homeassistant.components import mqtt
from homeassistant.components.mqtt.discovery import async_start
import homeassistant.components.sensor as sensor
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE
import homeassistant.core as ha
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry, assert_setup_component, async_fire_mqtt_message,
    async_mock_mqtt_component, fire_mqtt_message, get_test_home_assistant,
    mock_component, mock_mqtt_component, mock_registry)


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        """Test the setting of the value via MQTT."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        assert '100' == state.state
        assert 'fav unit' == \
            state.attributes.get('unit_of_measurement')

    @patch('homeassistant.core.dt_util.utcnow')
    def test_setting_sensor_value_expires(self, mock_utcnow):
        """Test the expiration of the value."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'expire_after': '4',
                'force_update': True
            }
        })

        state = self.hass.states.get('sensor.test')
        assert 'unknown' == state.state

        now = datetime(2017, 1, 1, 1, tzinfo=dt_util.UTC)
        mock_utcnow.return_value = now
        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()

        # Value was set correctly.
        state = self.hass.states.get('sensor.test')
        assert '100' == state.state

        # Time jump +3s
        now = now + timedelta(seconds=3)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is not yet expired
        state = self.hass.states.get('sensor.test')
        assert '100' == state.state

        # Next message resets timer
        mock_utcnow.return_value = now
        fire_mqtt_message(self.hass, 'test-topic', '101')
        self.hass.block_till_done()

        # Value was updated correctly.
        state = self.hass.states.get('sensor.test')
        assert '101' == state.state

        # Time jump +3s
        now = now + timedelta(seconds=3)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is not yet expired
        state = self.hass.states.get('sensor.test')
        assert '101' == state.state

        # Time jump +2s
        now = now + timedelta(seconds=2)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is expired now
        state = self.hass.states.get('sensor.test')
        assert 'unknown' == state.state

    def test_setting_sensor_value_via_mqtt_json_message(self):
        """Test the setting of the value via MQTT with JSON payload."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'value_template': '{{ value_json.val }}'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '{ "val": "100" }')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        assert '100' == state.state

    def test_force_update_disabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit'
            }
        })

        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        assert 1 == len(events)

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        assert 1 == len(events)

    def test_force_update_enabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'force_update': True
            }
        })

        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        assert 1 == len(events)

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        assert 2 == len(events)

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'availability_topic': 'availability-topic'
            }
        })

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE == state.state

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        })

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        assert STATE_UNAVAILABLE == state.state

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})

    def test_setting_sensor_attribute_via_mqtt_json_message(self):
        """Test the setting of attribute via MQTT with JSON payload."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'json_attributes': 'val'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '{ "val": "100" }')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        assert '100' == \
            state.attributes.get('val')

    @patch('homeassistant.components.mqtt.sensor._LOGGER')
    def test_update_with_json_attrs_not_dict(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'json_attributes': 'val'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '[ "list", "of", "things"]')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        assert state.attributes.get('val') is None
        assert mock_logger.warning.called

    @patch('homeassistant.components.mqtt.sensor._LOGGER')
    def test_update_with_json_attrs_bad_JSON(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'json_attributes': 'val'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', 'This is not JSON')
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        assert state.attributes.get('val') is None
        assert mock_logger.warning.called
        assert mock_logger.debug.called

    def test_update_with_json_attrs_and_template(self):
        """Test attributes get extracted from a JSON result."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'value_template': '{{ value_json.val }}',
                'json_attributes': 'val'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '{ "val": "100" }')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        assert '100' == \
            state.attributes.get('val')
        assert '100' == state.state

    def test_invalid_device_class(self):
        """Test device_class option with invalid value."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'mqtt',
                    'name': 'Test 1',
                    'state_topic': 'test-topic',
                    'device_class': 'foobarnotreal'
                }
            })

    def test_valid_device_class(self):
        """Test device_class option with valid values."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': [{
                'platform': 'mqtt',
                'name': 'Test 1',
                'state_topic': 'test-topic',
                'device_class': 'temperature'
            }, {
                'platform': 'mqtt',
                'name': 'Test 2',
                'state_topic': 'test-topic',
            }]
        })
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_1')
        assert state.attributes['device_class'] == 'temperature'
        state = self.hass.states.get('sensor.test_2')
        assert 'device_class' not in state.attributes


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    await hass.async_block_till_done()
    state = hass.states.get('sensor.test')

    assert '100' == state.attributes.get('val')


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    await hass.async_block_till_done()
    state = hass.states.get('sensor.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')
    await hass.async_block_till_done()

    state = hass.states.get('sensor.test')
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
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('sensor.beer')
    assert '100' == state.attributes.get('val')

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('sensor.beer')
    assert '100' == state.attributes.get('val')

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('sensor.beer')
    assert '75' == state.attributes.get('val')


async def test_unique_id(hass):
    """Test unique id option only creates one sensor per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: [{
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


async def test_discovery_removal_sensor(hass, mqtt_mock, caplog):
    """Test removal of discovered sensor."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('sensor.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('sensor.beer')
    assert state is None


async def test_discovery_update_sensor(hass, mqtt_mock, caplog):
    """Test update of discovered sensor."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('sensor.beer')
    assert state is not None
    assert state.name == 'Milk'

    state = hass.states.get('sensor.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic#" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('sensor.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('sensor.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT sensor device registry integration."""
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
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
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
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config',
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
    assert await async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'state_topic': 'test-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('sensor.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('sensor.beer', new_entity_id='sensor.milk')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('sensor.beer')
    assert state is None

    state = hass.states.get('sensor.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')


async def test_entity_device_info_with_hub(hass, mqtt_mock):
    """Test MQTT sensor device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)

    registry = await hass.helpers.device_registry.async_get_registry()
    hub = registry.async_get_or_create(
        config_entry_id='123',
        connections=set(),
        identifiers={('mqtt', 'hub-id')},
        manufacturer='manufacturer', model='hub'
    )

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'via_hub': 'hub-id',
        },
        'unique_id': 'veryunique'
    })
    async_fire_mqtt_message(hass, 'homeassistant/sensor/bla/config', data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.hub_device_id == hub.id
