"""
tests.components.test_influxdb
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests influxdb component.
"""
import copy
import unittest
from unittest import mock

import influxdb as influx_client

import homeassistant.components.influxdb as influxdb
from homeassistant.const import STATE_ON, STATE_OFF, EVENT_STATE_CHANGED


class TestInfluxDB(unittest.TestCase):
    @mock.patch('influxdb.InfluxDBClient')
    def test_setup_config_full(self, mock_client):
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
        hass = mock.MagicMock()
        self.assertTrue(influxdb.setup(hass, config))
        self.assertTrue(hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         hass.bus.listen.call_args_list[0][0][0])
        self.assertTrue(mock_client.return_value.query.called)

    @mock.patch('influxdb.InfluxDBClient')
    def test_setup_config_defaults(self, mock_client):
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        hass = mock.MagicMock()
        self.assertTrue(influxdb.setup(hass, config))
        self.assertTrue(hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         hass.bus.listen.call_args_list[0][0][0])

    @mock.patch('influxdb.InfluxDBClient')
    def test_setup_missing_keys(self, mock_client):
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        hass = mock.MagicMock()
        for missing in config['influxdb'].keys():
            config_copy = copy.deepcopy(config)
            del config_copy['influxdb'][missing]
            self.assertFalse(influxdb.setup(hass, config_copy))

    @mock.patch('influxdb.InfluxDBClient')
    def test_setup_query_fail(self, mock_client):
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        hass = mock.MagicMock()
        mock_client.return_value.query.side_effect = \
            influx_client.exceptions.InfluxDBClientError('fake')
        self.assertFalse(influxdb.setup(hass, config))

    def _setup(self, mock_influx):
        self.mock_client = mock_influx.return_value
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
            }
        }
        self.hass = mock.MagicMock()
        influxdb.setup(self.hass, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    @mock.patch('influxdb.InfluxDBClient')
    def test_event_listener(self, mock_influx):
        self._setup(mock_influx)

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0,
                 'foo': 'foo'}
        for in_, out in valid.items():
            attrs = {'unit_of_measurement': 'foobars'}
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
                },
            }]
            self.handler_method(event)
            self.mock_client.write_points.assert_called_once_with(body)
            self.mock_client.write_points.reset_mock()

    @mock.patch('influxdb.InfluxDBClient')
    def test_event_listener_no_units(self, mock_influx):
        self._setup(mock_influx)

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
            self.mock_client.write_points.assert_called_once_with(body)
            self.mock_client.write_points.reset_mock()

    @mock.patch('influxdb.InfluxDBClient')
    def test_event_listener_fail_write(self, mock_influx):
        self._setup(mock_influx)

        state = mock.MagicMock(state=1,
                               domain='fake',
                               entity_id='entity-id',
                               object_id='entity',
                               attributes={})
        event = mock.MagicMock(data={'new_state': state},
                               time_fired=12345)
        self.mock_client.write_points.side_effect = \
            influx_client.exceptions.InfluxDBClientError('foo')
        self.handler_method(event)
