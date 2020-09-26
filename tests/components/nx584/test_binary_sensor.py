"""The tests for the nx584 sensor platform."""
import unittest
from unittest import mock

from nx584 import client as nx584_client
import pytest
import requests

from homeassistant.components.nx584 import binary_sensor as nx584
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class StopMe(Exception):
    """Stop helper."""

    pass


class TestNX584SensorSetup(unittest.TestCase):
    """Test the NX584 sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self._mock_client = mock.patch.object(nx584_client, "Client")
        self._mock_client.start()

        self.fake_zones = [
            {"name": "front", "number": 1},
            {"name": "back", "number": 2},
            {"name": "inside", "number": 3},
        ]

        client = nx584_client.Client.return_value
        client.list_zones.return_value = self.fake_zones
        client.get_version.return_value = "1.1"
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()
        self._mock_client.stop()

    @mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher")
    @mock.patch("homeassistant.components.nx584.binary_sensor.NX584ZoneSensor")
    def test_setup_defaults(self, mock_nx, mock_watcher):
        """Test the setup with no configuration."""
        add_entities = mock.MagicMock()
        config = {
            "host": nx584.DEFAULT_HOST,
            "port": nx584.DEFAULT_PORT,
            "exclude_zones": [],
            "zone_types": {},
        }
        assert nx584.setup_platform(self.hass, config, add_entities)
        mock_nx.assert_has_calls(
            [mock.call(zone, "opening") for zone in self.fake_zones]
        )
        assert add_entities.called
        assert nx584_client.Client.call_count == 1
        assert nx584_client.Client.call_args == mock.call("http://localhost:5007")

    @mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher")
    @mock.patch("homeassistant.components.nx584.binary_sensor.NX584ZoneSensor")
    def test_setup_full_config(self, mock_nx, mock_watcher):
        """Test the setup with full configuration."""
        config = {
            "host": "foo",
            "port": 123,
            "exclude_zones": [2],
            "zone_types": {3: "motion"},
        }
        add_entities = mock.MagicMock()
        assert nx584.setup_platform(self.hass, config, add_entities)
        mock_nx.assert_has_calls(
            [
                mock.call(self.fake_zones[0], "opening"),
                mock.call(self.fake_zones[2], "motion"),
            ]
        )
        assert add_entities.called
        assert nx584_client.Client.call_count == 1
        assert nx584_client.Client.call_args == mock.call("http://foo:123")
        assert mock_watcher.called

    def _test_assert_graceful_fail(self, config):
        """Test the failing."""
        assert not setup_component(self.hass, "nx584", config)

    def test_setup_bad_config(self):
        """Test the setup with bad configuration."""
        bad_configs = [
            {"exclude_zones": ["a"]},
            {"zone_types": {"a": "b"}},
            {"zone_types": {1: "notatype"}},
            {"zone_types": {"notazone": "motion"}},
        ]
        for config in bad_configs:
            self._test_assert_graceful_fail(config)

    def test_setup_connect_failed(self):
        """Test the setup with connection failure."""
        nx584_client.Client.return_value.list_zones.side_effect = (
            requests.exceptions.ConnectionError
        )
        self._test_assert_graceful_fail({})

    def test_setup_no_partitions(self):
        """Test the setup with connection failure."""
        nx584_client.Client.return_value.list_zones.side_effect = IndexError
        self._test_assert_graceful_fail({})

    def test_setup_version_too_old(self):
        """Test if version is too old."""
        nx584_client.Client.return_value.get_version.return_value = "1.0"
        self._test_assert_graceful_fail({})

    def test_setup_no_zones(self):
        """Test the setup with no zones."""
        nx584_client.Client.return_value.list_zones.return_value = []
        add_entities = mock.MagicMock()
        assert nx584.setup_platform(self.hass, {}, add_entities)
        assert not add_entities.called


class TestNX584ZoneSensor(unittest.TestCase):
    """Test for the NX584 zone sensor."""

    def test_sensor_normal(self):
        """Test the sensor."""
        zone = {"number": 1, "name": "foo", "state": True}
        sensor = nx584.NX584ZoneSensor(zone, "motion")
        assert "foo" == sensor.name
        assert not sensor.should_poll
        assert sensor.is_on
        assert sensor.device_state_attributes["zone_number"] == 1

        zone["state"] = False
        assert not sensor.is_on


class TestNX584Watcher(unittest.TestCase):
    """Test the NX584 watcher."""

    @mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
    def test_process_zone_event(self, mock_update):
        """Test the processing of zone events."""
        zone1 = {"number": 1, "name": "foo", "state": True}
        zone2 = {"number": 2, "name": "bar", "state": True}
        zones = {
            1: nx584.NX584ZoneSensor(zone1, "motion"),
            2: nx584.NX584ZoneSensor(zone2, "motion"),
        }
        watcher = nx584.NX584Watcher(None, zones)
        watcher._process_zone_event({"zone": 1, "zone_state": False})
        assert not zone1["state"]
        assert mock_update.call_count == 1

    @mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
    def test_process_zone_event_missing_zone(self, mock_update):
        """Test the processing of zone events with missing zones."""
        watcher = nx584.NX584Watcher(None, {})
        watcher._process_zone_event({"zone": 1, "zone_state": False})
        assert not mock_update.called

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
            {"zone": 1, "zone_state": True, "type": "zone_status"},
            {"zone": 2, "foo": False},
        ]
        client.get_events.side_effect = fake_get_events
        watcher = nx584.NX584Watcher(client, {})

        @mock.patch.object(watcher, "_process_zone_event")
        def run(fake_process):
            """Run a fake process."""
            fake_process.side_effect = StopMe
            with pytest.raises(StopMe):
                watcher._run()
            assert fake_process.call_count == 1
            assert fake_process.call_args == mock.call(fake_events[0])

        run()
        assert 3 == client.get_events.call_count

    @mock.patch("time.sleep")
    def test_run_retries_failures(self, mock_sleep):
        """Test the retries with failures."""
        empty_me = [1, 2]

        def fake_run():
            """Fake runner."""
            if empty_me:
                empty_me.pop()
                raise requests.exceptions.ConnectionError()
            raise StopMe()

        watcher = nx584.NX584Watcher(None, {})
        with mock.patch.object(watcher, "_run") as mock_inner:
            mock_inner.side_effect = fake_run
            with pytest.raises(StopMe):
                watcher.run()
            assert 3 == mock_inner.call_count
        mock_sleep.assert_has_calls([mock.call(10), mock.call(10)])
