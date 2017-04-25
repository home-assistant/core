"""The tests for the InfluxDB component."""
import unittest
from unittest import mock

import influxdb as influx_client

from homeassistant.setup import setup_component
import homeassistant.components.influxdb as influxdb
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON

from tests.common import get_test_home_assistant


@mock.patch('influxdb.InfluxDBClient')
class TestInfluxDB(unittest.TestCase):
    """Test the InfluxDB component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.handler_method = None
        self.hass.bus.listen = mock.Mock()

    def tearDown(self):
        """Clear data."""
        self.hass.stop()

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
        self.assertEqual(
            EVENT_STATE_CHANGED, self.hass.bus.listen.call_args_list[0][0][0])
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
        self.assertEqual(
            EVENT_STATE_CHANGED, self.hass.bus.listen.call_args_list[0][0][0])

    def test_setup_minimal_config(self, mock_client):
        """Test the setup with minimal configuration."""
        config = {
            'influxdb': {}
        }

        assert setup_component(self.hass, influxdb.DOMAIN, config)

    def test_setup_missing_password(self, mock_client):
        """Test the setup with existing username and missing password."""
        config = {
            'influxdb': {
                'username': 'user'
            }
        }

        assert not setup_component(self.hass, influxdb.DOMAIN, config)

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
                'exclude': {
                    'entities': ['fake.blacklisted'],
                    'domains': ['another_fake']
                }
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    def test_event_listener(self, mock_client):
        """Test the event listener."""
        self._setup()

        valid = {
            '1': 1,
            '1.0': 1.0,
            STATE_ON: 1,
            STATE_OFF: 0,
            'foo': 'foo'
        }
        for in_, out in valid.items():
            attrs = {
                'unit_of_measurement': 'foobars',
                'longitude': '1.1',
                'latitude': '2.2'
            }
            state = mock.MagicMock(
                state=in_, domain='fake', object_id='entity', attributes=attrs)
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
            if isinstance(out, str):
                body = [{
                    'measurement': 'foobars',
                    'tags': {
                        'domain': 'fake',
                        'entity_id': 'entity',
                    },
                    'time': 12345,
                    'fields': {
                        'state': out,
                        'longitude': 1.1,
                        'latitude': 2.2
                    },
                }]

            else:
                body = [{
                    'measurement': 'foobars',
                    'tags': {
                        'domain': 'fake',
                        'entity_id': 'entity',
                    },
                    'time': 12345,
                    'fields': {
                        'value': out,
                        'longitude': 1.1,
                        'latitude': 2.2
                    },
                }]
            self.handler_method(event)
            self.assertEqual(
                mock_client.return_value.write_points.call_count, 1
            )
            self.assertEqual(
                mock_client.return_value.write_points.call_args,
                mock.call(body)
            )
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_no_units(self, mock_client):
        """Test the event listener for missing units."""
        self._setup()

        for unit in (None, ''):
            if unit:
                attrs = {'unit_of_measurement': unit}
            else:
                attrs = {}
            state = mock.MagicMock(
                state=1, domain='fake', entity_id='entity-id',
                object_id='entity', attributes=attrs)
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
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
            self.assertEqual(
                mock_client.return_value.write_points.call_count, 1
            )
            self.assertEqual(
                mock_client.return_value.write_points.call_args,
                mock.call(body)
            )
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_fail_write(self, mock_client):
        """Test the event listener for write failures."""
        self._setup()

        state = mock.MagicMock(
            state=1, domain='fake', entity_id='entity-id', object_id='entity',
            attributes={})
        event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
        mock_client.return_value.write_points.side_effect = \
            influx_client.exceptions.InfluxDBClientError('foo')
        self.handler_method(event)

    def test_event_listener_states(self, mock_client):
        """Test the event listener against ignored states."""
        self._setup()

        for state_state in (1, 'unknown', '', 'unavailable'):
            state = mock.MagicMock(
                state=state_state, domain='fake', entity_id='entity-id',
                object_id='entity', attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
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
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_blacklist(self, mock_client):
        """Test the event listener against a blacklist."""
        self._setup()

        for entity_id in ('ok', 'blacklisted'):
            state = mock.MagicMock(
                state=1, domain='fake', entity_id='fake.{}'.format(entity_id),
                object_id=entity_id, attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
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
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_blacklist_domain(self, mock_client):
        """Test the event listener against a blacklist."""
        self._setup()

        for domain in ('ok', 'another_fake'):
            state = mock.MagicMock(
                state=1, domain=domain,
                entity_id='{}.something'.format(domain),
                object_id='something', attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
            body = [{
                'measurement': '{}.something'.format(domain),
                'tags': {
                    'domain': domain,
                    'entity_id': 'something',
                },
                'time': 12345,
                'fields': {
                    'value': 1,
                },
            }]
            self.handler_method(event)
            if domain == 'ok':
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_whitelist(self, mock_client):
        """Test the event listener against a whitelist."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
                'include': {
                    'entities': ['fake.included'],
                }
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        for entity_id in ('included', 'default'):
            state = mock.MagicMock(
                state=1, domain='fake', entity_id='fake.{}'.format(entity_id),
                object_id=entity_id, attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
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
            if entity_id == 'included':
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_whitelist_domain(self, mock_client):
        """Test the event listener against a whitelist."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
                'include': {
                    'domains': ['fake'],
                }
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        for domain in ('fake', 'another_fake'):
            state = mock.MagicMock(
                state=1, domain=domain,
                entity_id='{}.something'.format(domain),
                object_id='something', attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
            body = [{
                'measurement': '{}.something'.format(domain),
                'tags': {
                    'domain': domain,
                    'entity_id': 'something',
                },
                'time': 12345,
                'fields': {
                    'value': 1,
                },
            }]
            self.handler_method(event)
            if domain == 'fake':
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_invalid_type(self, mock_client):
        """Test the event listener when an attirbute has an invalid type."""
        self._setup()

        valid = {
            '1': 1,
            '1.0': 1.0,
            STATE_ON: 1,
            STATE_OFF: 0,
            'foo': 'foo'
        }
        for in_, out in valid.items():
            attrs = {
                'unit_of_measurement': 'foobars',
                'longitude': '1.1',
                'latitude': '2.2',
                'invalid_attribute': ['value1', 'value2']
            }
            state = mock.MagicMock(
                state=in_, domain='fake', object_id='entity', attributes=attrs)
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
            if isinstance(out, str):
                body = [{
                    'measurement': 'foobars',
                    'tags': {
                        'domain': 'fake',
                        'entity_id': 'entity',
                    },
                    'time': 12345,
                    'fields': {
                        'state': out,
                        'longitude': 1.1,
                        'latitude': 2.2,
                        'invalid_attribute_str': "['value1', 'value2']"
                    },
                }]

            else:
                body = [{
                    'measurement': 'foobars',
                    'tags': {
                        'domain': 'fake',
                        'entity_id': 'entity',
                    },
                    'time': 12345,
                    'fields': {
                        'value': float(out),
                        'longitude': 1.1,
                        'latitude': 2.2,
                        'invalid_attribute_str': "['value1', 'value2']"
                    },
                }]
            self.handler_method(event)
            self.assertEqual(
                mock_client.return_value.write_points.call_count, 1
            )
            self.assertEqual(
                mock_client.return_value.write_points.call_args,
                mock.call(body)
            )
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_default_measurement(self, mock_client):
        """Test the event listener with a default measurement."""
        config = {
            'influxdb': {
                'host': 'host',
                'username': 'user',
                'password': 'pass',
                'default_measurement': 'state',
                'exclude': {
                    'entities': ['fake.blacklisted']
                }
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        for entity_id in ('ok', 'blacklisted'):
            state = mock.MagicMock(
                state=1, domain='fake', entity_id='fake.{}'.format(entity_id),
                object_id=entity_id, attributes={})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)
            body = [{
                'measurement': 'state',
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
                self.assertEqual(
                    mock_client.return_value.write_points.call_count, 1
                )
                self.assertEqual(
                    mock_client.return_value.write_points.call_args,
                    mock.call(body)
                )
            else:
                self.assertFalse(mock_client.return_value.write_points.called)
            mock_client.return_value.write_points.reset_mock()
