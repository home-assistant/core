"""The tests for the nx584 sensor platform."""
import requests
import unittest
from unittest import mock

from nx584 import client as nx584_client

from homeassistant.components.binary_sensor import nx584
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class StopMe(Exception):
    """Stop helper."""

    pass


class TestNX584SensorSetup(unittest.TestCase):
    """Test the NX584 sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
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
        """Stop everything that was started."""
        self.hass.stop()
        self._mock_client.stop()

    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584Watcher')
    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584ZoneSensor')
    def test_setup_defaults(self, mock_nx, mock_watcher):
        """Test the setup with no configuration."""
        add_devices = mock.MagicMock()
        config = {
            'host': nx584.DEFAULT_HOST,
            'port': nx584.DEFAULT_PORT,
            'exclude_zones': [],
            'zone_types': {},
            }
        self.assertTrue(nx584.setup_platform(self.hass, config, add_devices))
        mock_nx.assert_has_calls(
             [mock.call(zone, 'opening') for zone in self.fake_zones])
        self.assertTrue(add_devices.called)
        self.assertEqual(nx584_client.Client.call_count, 1)
        self.assertEqual(
            nx584_client.Client.call_args, mock.call('http://localhost:5007')
        )

    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584Watcher')
    @mock.patch('homeassistant.components.binary_sensor.nx584.NX584ZoneSensor')
    def test_setup_full_config(self, mock_nx, mock_watcher):
        """Test the setup with full configuration."""
        config = {
            'host': 'foo',
            'port': 123,
            'exclude_zones': [2],
            'zone_types': {3: 'motion'},
            }
        add_devices = mock.MagicMock()
        self.assertTrue(nx584.setup_platform(self.hass, config, add_devices))
        mock_nx.assert_has_calls([
            mock.call(self.fake_zones[0], 'opening'),
            mock.call(self.fake_zones[2], 'motion'),
            ])
        self.assertTrue(add_devices.called)
        self.assertEqual(nx584_client.Client.call_count, 1)
        self.assertEqual(
            nx584_client.Client.call_args, mock.call('http://foo:123')
        )
        self.assertTrue(mock_watcher.called)

    def _test_assert_graceful_fail(self, config):
        """Test the failing."""
        self.assertFalse(setup_component(
            self.hass, 'binary_sensor.nx584', config))

    def test_setup_bad_config(self):
        """Test the setup with bad configuration."""
        bad_configs = [
            {'exclude_zones': ['a']},
            {'zone_types': {'a': 'b'}},
            {'zone_types': {1: 'notatype'}},
            {'zone_types': {'notazone': 'motion'}},
        ]
        for config in bad_configs:
            self._test_assert_graceful_fail(config)

    def test_setup_connect_failed(self):
        """Test the setup with connection failure."""
        nx584_client.Client.return_value.list_zones.side_effect = \
            requests.exceptions.ConnectionError
        self._test_assert_graceful_fail({})

    def test_setup_no_partitions(self):
        """Test the setup with connection failure."""
        nx584_client.Client.return_value.list_zones.side_effect = \
            IndexError
        self._test_assert_graceful_fail({})

    def test_setup_version_too_old(self):
        """"Test if version is too old."""
        nx584_client.Client.return_value.get_version.return_value = '1.0'
        self._test_assert_graceful_fail({})

    def test_setup_no_zones(self):
        """Test the setup with no zones."""
        nx584_client.Client.return_value.list_zones.return_value = []
        add_devices = mock.MagicMock()
        self.assertTrue(nx584.setup_platform(self.hass, {}, add_devices))
        self.assertFalse(add_devices.called)


class TestNX584ZoneSensor(unittest.TestCase):
    """Test for the NX584 zone sensor."""

    def test_sensor_normal(self):
        """Test the sensor."""
        zone = {'number': 1, 'name': 'foo', 'state': True}
        sensor = nx584.NX584ZoneSensor(zone, 'motion')
        self.assertEqual('foo', sensor.name)
        self.assertFalse(sensor.should_poll)
        self.assertTrue(sensor.is_on)

        zone['state'] = False
        self.assertFalse(sensor.is_on)


class TestNX584Watcher(unittest.TestCase):
    """Test the NX584 watcher."""

    @mock.patch.object(nx584.NX584ZoneSensor, 'schedule_update_ha_state')
    def test_process_zone_event(self, mock_update):
        """Test the processing of zone events."""
        zone1 = {'number': 1, 'name': 'foo', 'state': True}
        zone2 = {'number': 2, 'name': 'bar', 'state': True}
        zones = {
            1: nx584.NX584ZoneSensor(zone1, 'motion'),
            2: nx584.NX584ZoneSensor(zone2, 'motion'),
        }
        watcher = nx584.NX584Watcher(None, zones)
        watcher._process_zone_event({'zone': 1, 'zone_state': False})
        self.assertFalse(zone1['state'])
        self.assertEqual(1, mock_update.call_count)

    @mock.patch.object(nx584.NX584ZoneSensor, 'schedule_update_ha_state')
    def test_process_zone_event_missing_zone(self, mock_update):
        """Test the processing of zone events with missing zones."""
        watcher = nx584.NX584Watcher(None, {})
        watcher._process_zone_event({'zone': 1, 'zone_state': False})
        self.assertFalse(mock_update.called)

    def test_run_with_zone_events(self):
        """Test the zone events."""
        empty_me = [1, 2]

        def fake_get_events():
            """Return nothing twice, then some events."""
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
            """Run a fake process."""
            fake_process.side_effect = StopMe
            self.assertRaises(StopMe, watcher._run)
            self.assertEqual(fake_process.call_count, 1)
            self.assertEqual(fake_process.call_args, mock.call(fake_events[0]))

        run()
        self.assertEqual(3, client.get_events.call_count)

    @mock.patch('time.sleep')
    def test_run_retries_failures(self, mock_sleep):
        """Test the retries with failures."""
        empty_me = [1, 2]

        def fake_run():
            """Fake runner."""
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
