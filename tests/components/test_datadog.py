"""The tests for the Datadog component."""
from unittest import mock
import unittest

import voluptuous as vol

from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON
)
from homeassistant.setup import setup_component
import homeassistant.components.datadog as datadog
import homeassistant.core as ha

from tests.common import get_test_home_assistant


class TestDatadog(unittest.TestCase):
    """Test the Datadog component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_config(self):
        """Test configuration with defaults."""
        config = {
            'datadog': {
                'host1': 'host1',
            }
        }

        with self.assertRaises(vol.Invalid):
            datadog.CONFIG_SCHEMA(None)
        with self.assertRaises(vol.Invalid):
            datadog.CONFIG_SCHEMA(config)

    @mock.patch('datadog.initialize')
    def test_datadog_setup_full(self, mock_connection):
        """Test setup with all data."""
        config = {
            'datadog': {
                'host': 'host',
                'port': 123,
                'rate': 1,
                'prefix': 'foo',
            }
        }
        self.hass.bus.listen = mock.MagicMock()
        self.assertTrue(setup_component(self.hass, datadog.DOMAIN, config))
        self.assertEqual(mock_connection.call_count, 1)
        self.assertEqual(
            mock_connection.call_args,
            mock.call(statsd_host='host', statsd_port=123)
        )

        self.assertTrue(self.hass.bus.listen.called)
        self.assertEqual(EVENT_LOGBOOK_ENTRY,
                         self.hass.bus.listen.call_args_list[0][0][0])
        self.assertEqual(EVENT_STATE_CHANGED,
                         self.hass.bus.listen.call_args_list[1][0][0])

    @mock.patch('datadog.initialize')
    def test_datadog_setup_defaults(self, mock_connection):
        """Test setup with defaults."""
        config = {
            'datadog': {
                'host': 'host',
            }
        }

        config['datadog'][datadog.CONF_PORT] = datadog.DEFAULT_PORT
        config['datadog'][datadog.CONF_PREFIX] = datadog.DEFAULT_PREFIX

        self.hass.bus.listen = mock.MagicMock()
        self.assertTrue(setup_component(self.hass, datadog.DOMAIN, config))
        self.assertEqual(mock_connection.call_count, 1)
        self.assertEqual(
            mock_connection.call_args,
            mock.call(statsd_host='host', statsd_port=8125)
        )
        self.assertTrue(self.hass.bus.listen.called)

    @mock.patch('datadog.statsd')
    def test_logbook_entry(self, mock_client):
        """Test event listener."""
        config = {
            'datadog': {
                'host': 'host'
            }
        }

        config['datadog'][datadog.CONF_RATE] = datadog.DEFAULT_RATE

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, datadog.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        event = {
            'domain': 'automation',
            'entity_id': 'sensor.foo.bar',
            'message': 'foo bar biz',
            'name': 'triggered something'
        }
        handler_method(mock.MagicMock(data=event))

        self.assertEqual(mock_client.event.call_count, 1)
        self.assertEqual(
            mock_client.event.call_args,
            mock.call(
                title="Home Assistant",
                text="%%% \n **{}** {} \n %%%".format(
                    event['name'],
                    event['message']
                ),
                tags=["entity:sensor.foo.bar", "domain:automation"]
            )
        )

        mock_client.event.reset_mock()

    @mock.patch('datadog.statsd')
    def test_state_changed(self, mock_client):
        """Test event listener."""
        config = {
            'datadog': {
                'host': 'host',
                'prefix': 'ha'
            }
        }

        config['datadog'][datadog.CONF_RATE] = datadog.DEFAULT_RATE

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, datadog.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        handler_method = self.hass.bus.listen.call_args_list[1][0][1]

        valid = {
            '1': 1,
            '1.0': 1.0,
            STATE_ON: 1,
            STATE_OFF: 0
        }

        attributes = {
            'elevation': 3.2,
            'temperature': 5.0
        }

        for in_, out in valid.items():
            state = mock.MagicMock(domain="sensor", entity_id="sensor.foo.bar",
                                   state=in_, attributes=attributes)
            handler_method(mock.MagicMock(data={'new_state': state}))

            self.assertEqual(mock_client.gauge.call_count, 3)

            for attribute, value in attributes.items():
                mock_client.gauge.assert_has_calls([
                    mock.call(
                        "ha.sensor.{}".format(attribute),
                        value,
                        sample_rate=1,
                        tags=["entity:{}".format(state.entity_id)]
                    )
                ])

            self.assertEqual(
                mock_client.gauge.call_args,
                mock.call("ha.sensor", out, sample_rate=1, tags=[
                    "entity:{}".format(state.entity_id)
                ])
            )

            mock_client.gauge.reset_mock()

        for invalid in ('foo', '', object):
            handler_method(mock.MagicMock(data={
                'new_state': ha.State('domain.test', invalid, {})}))
            self.assertFalse(mock_client.gauge.called)
