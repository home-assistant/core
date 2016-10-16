"""The tests for the InfluxDB component."""
import copy
import unittest
from unittest import mock

import influxdb as influx_client

from homeassistant.bootstrap import setup_component
import homeassistant.components.influxdb as influxdb
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON


@mock.patch('influxdb.InfluxDBClient')
class TestInfluxDB(unittest.TestCase):
    """Test the InfluxDB component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = mock.MagicMock()
        self.hass.pool.worker_count = 2
        self.handler_method = None

    def test_setup_config_full(self, mock_client):
        """Test the setup with full configuration."""
        config = {
            'influxdb': {
                'host': 'host',
                'port': 123,
                'database': 'db',
                'username': 'user',
                'password': 'password',
                'ssl': 'False',
                'verify_ssl': 'False',
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         self.hass.bus.listen.call_args_list[0][0][0])
        self.assertTrue(mock_client.return_value.query.called)

    def test_setup_config_defaults(self, mock_client):
        """Test the setup with default configuration."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         self.hass.bus.listen.call_args_list[0][0][0])

    def test_setup_missing_keys(self, mock_client):
        """Test the setup with missing keys."""
        config = {
            'influxdb': {
                'username': 'user',
                'password': 'pass',
            }
        }
        for missing in config['influxdb'].keys():
            config_copy = copy.deepcopy(config)
            del config_copy['influxdb'][missing]
            assert not setup_component(self.hass, influxdb.DOMAIN, config_copy)

    def test_setup_query_fail(self, mock_client):
        """Test the setup for query failures."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        mock_client.return_value.query.side_effect = \
            influx_client.exceptions.InfluxDBClientError('fake')
        assert not setup_component(self.hass, influxdb.DOMAIN, config)

    def _setup(self):
        """Setup the client."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
                'blacklist': ['fake.blacklisted']
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    def test_event_listener(self, mock_client):
        """Test the event listener."""
        self._setup()

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0,
                 'foo': 'foo'}
        for in_, out in valid.items():
            attrs = {
                        'unit_of_measurement': 'foobars',
                        'longitude': '1.1',
                        'latitude': '2.2'
                    }
            state = mock.MagicMock(state=in_,
                                   domain='fake',
                                   object_id='entity',
                                   attributes=attrs)
            event = mock.MagicMock(data={'new_state': state},
                                   time_fired=12345)
            body = [{
                'measurement': 'foobars',
                'tags': {
                    'domain': 'fake',
                    'entity_id': 'entity',
                },
                'time': 12345,
                'fields': {
                    'value': out,
                    'longitude': '1.1',
                    'latitude': '2.2'
                },
            }]
            self.handler_method(event)
            mock_client.return_value.write_points.assert_called_once_with(body)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_no_units(self, mock_client):
        """Test the event listener for missing units."""
        self._setup()

        for unit in (None, ''):
            if unit:
                attrs = {'unit_of_measurement': unit}
            else:
                attrs = {}
            state = mock.MagicMock(state=1,
                                   domain='fake',
                                   entity_id='entity-id',
                                   object_id='entity',
                                   attributes=attrs)
            event = mock.MagicMock(data={'new_state': state},
                                   time_fired=12345)
            body = [{
                'measurement': 'entity-id',
                'tags': {
                    'domain': 'fake',
                    'entity_id': 'entity',
                },
                'time': 12345,
                'fields': {
                    'value': 1,
                },
            }]
            self.handler_method(event)
            mock_client.return_value.write_points.assert_called_once_with(body)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_fail_write(self, mock_client):
        """Test the event listener for write failures."""
        self._setup()

        state = mock.MagicMock(state=1,
                               domain='fake',
                               entity_id='entity-id',
                               object_id='entity',
                               attributes={})
        event = mock.MagicMock(data={'new_state': state},
                               time_fired=12345)
        mock_client.return_value.write_points.side_effect = \
            influx_client.exceptions.InfluxDBClientError('foo')
        self.handler_method(event)

    def test_event_listener_states(self, mock_client):
        """Test the event listener against ignored states."""
        self._setup()

        for state_state in (1, 'unknown', '', 'unavailable'):
            state = mock.MagicMock(state=state_state,
                                   domain='fake',
                                   entity_id='entity-id',
                                   object_id='entity',
                                   attributes={})
            event = mock.MagicMock(data={'new_state': state},
                                   time_fired=12345)
            body = [{
                'measurement': 'entity-id',
                'tags': {
                    'domain': 'fake',
                    'entity_id': 'entity',
                },
                'time': 12345,
                'fields': {
                    'value': 1,
                },
            }]
            self.handler_method(event)
            if state_state == 1:
                mock_client.return_value.write_points.assert_called_once_with(
                    body)
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_blacklist(self, mock_client):
        """Test the event listener against a blacklist."""
        self._setup()

        for entity_id in ('ok', 'blacklisted'):
            state = mock.MagicMock(state=1,
                                   domain='fake',
                                   entity_id='fake.{}'.format(entity_id),
                                   object_id=entity_id,
                                   attributes={})
            event = mock.MagicMock(data={'new_state': state},
                                   time_fired=12345)
            body = [{
                'measurement': 'fake.{}'.format(entity_id),
                'tags': {
                    'domain': 'fake',
                    'entity_id': entity_id,
                },
                'time': 12345,
                'fields': {
                    'value': 1,
                },
            }]
            self.handler_method(event)
            if entity_id == 'ok':
                mock_client.return_value.write_points.assert_called_once_with(
                    body)
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()
