"""
tests.components.binary_sensor.nx584
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for nx584 sensor.
"""

import requests
import unittest
from unittest import mock

from homeassistant.components.binary_sensor import nx584
from nx584 import client as nx584_client


class StopMe(Exception):
    pass


class TestNX584SensorSetup(unittest.TestCase):
    def setUp(self):
        self._mock_client = mock.patch.object(nx584_client, 'Client')
        self._mock_client.start()

        self.fake_zones = [
            {'name': 'front', 'number': 1},
            {'name': 'back', 'number': 2},
            {'name': 'inside', 'number': 3},
            ]

        client = nx584_client.Client.return_value
        client.list_zones.return_value = self.fake_zones
        client.get_version.return_value = '1.1'

    def tearDown(self):
        self._mock_client.stop()

    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584Watcher')
    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584ZoneSensor')
    def test_setup_no_config(self, mock_nx, mock_watcher):
        add_devices = mock.MagicMock()
        hass = mock.MagicMock()
        self.assertTrue(nx584.setup_platform(hass, {}, add_devices))
        mock_nx.assert_has_calls([
            mock.call(zone)
            for zone in self.fake_zones])
        self.assertTrue(add_devices.called)
        nx584_client.Client.assert_called_once_with('http://localhost:5007')

    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584Watcher')
    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584ZoneSensor')
    def test_setup_full_config(self, mock_nx, mock_watcher):
        config = {
            'host': 'foo:123',
            'exclude_zones': [2],
            'zone_types': {3: 'motion'},
            }
        add_devices = mock.MagicMock()
        hass = mock.MagicMock()
        self.assertTrue(nx584.setup_platform(hass, config, add_devices))
        mock_nx.assert_has_calls([
            mock.call(self.fake_zones[0]),
            mock.call(self.fake_zones[2]),
            ])
        self.assertTrue(add_devices.called)
        nx584_client.Client.assert_called_once_with('http://foo:123')
        self.assertTrue(mock_watcher.called)

    def _test_assert_graceful_fail(self, config):
        hass = add_devices = mock.MagicMock()
        self.assertFalse(nx584.setup_platform(hass, config,
                                              add_devices))
        self.assertFalse(add_devices.called)

    def test_setup_bad_config(self):
        bad_configs = [
            {'exclude_zones': ['a']},
        ]
        for config in bad_configs:
            self._test_assert_graceful_fail(config)

    def test_setup_connect_failed(self):
        nx584_client.Client.return_value.list_zones.side_effect = \
            requests.exceptions.ConnectionError
        self._test_assert_graceful_fail({})

    def test_setup_version_too_old(self):
        nx584_client.Client.return_value.get_version.return_value = '1.0'
        self._test_assert_graceful_fail({})

    def test_setup_no_zones(self):
        nx584_client.Client.return_value.list_zones.return_value = []
        hass = add_devices = mock.MagicMock()
        self.assertTrue(nx584.setup_platform(hass, {},
                                             add_devices))
        self.assertFalse(add_devices.called)


class TestNX584ZoneSensor(unittest.TestCase):
    def test_sensor_normal(self):
        zone = {'number': 1, 'name': 'foo', 'state': True}
        sensor = nx584.NX584ZoneSensor(zone)
        self.assertEqual('foo', sensor.name)
        self.assertFalse(sensor.should_poll)
        self.assertTrue(sensor.is_on)

        zone['state'] = False
        self.assertFalse(sensor.is_on)


class TestNX584Watcher(unittest.TestCase):
    @mock.patch.object(nx584.NX584ZoneSensor, 'update_ha_state')
    def test_process_zone_event(self, mock_update):
        zone1 = {'number': 1, 'name': 'foo', 'state': True}
        zone2 = {'number': 2, 'name': 'bar', 'state': True}
        zones = {
            1: nx584.NX584ZoneSensor(zone1),
            2: nx584.NX584ZoneSensor(zone2),
        }
        watcher = nx584.NX584Watcher(None, zones)
        watcher._process_zone_event({'zone': 1, 'zone_state': False})
        self.assertFalse(zone1['state'])
        self.assertEqual(1, mock_update.call_count)

    @mock.patch.object(nx584.NX584ZoneSensor, 'update_ha_state')
    def test_process_zone_event_missing_zone(self, mock_update):
        watcher = nx584.NX584Watcher(None, {})
        watcher._process_zone_event({'zone': 1, 'zone_state': False})
        self.assertFalse(mock_update.called)

    def test_run_with_zone_events(self):
        empty_me = [1, 2]

        def fake_get_events():
            """Return nothing twice, then some events"""
            if empty_me:
                empty_me.pop()
            else:
                return fake_events

        client = mock.MagicMock()
        fake_events = [
            {'zone': 1, 'zone_state': True, 'type': 'zone_status'},
            {'zone': 2, 'foo': False},
        ]
        client.get_events.side_effect = fake_get_events
        watcher = nx584.NX584Watcher(client, {})

        @mock.patch.object(watcher, '_process_zone_event')
        def run(fake_process):
            fake_process.side_effect = StopMe
            self.assertRaises(StopMe, watcher._run)
            fake_process.assert_called_once_with(fake_events[0])

        run()
        self.assertEqual(3, client.get_events.call_count)

    @mock.patch('time.sleep')
    def test_run_retries_failures(self, mock_sleep):
        empty_me = [1, 2]

        def fake_run():
            if empty_me:
                empty_me.pop()
                raise requests.exceptions.ConnectionError()
            else:
                raise StopMe()

        watcher = nx584.NX584Watcher(None, {})
        with mock.patch.object(watcher, '_run') as mock_inner:
            mock_inner.side_effect = fake_run
            self.assertRaises(StopMe, watcher.run)
            self.assertEqual(3, mock_inner.call_count)
        mock_sleep.assert_has_calls([mock.call(10), mock.call(10)])
