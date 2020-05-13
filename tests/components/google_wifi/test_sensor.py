"""The tests for the Google Wifi platform."""
from datetime import datetime, timedelta
import unittest

import requests_mock

from homeassistant import core as ha
import homeassistant.components.google_wifi.sensor as google_wifi
from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import setup_component
from homeassistant.util import dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import assert_setup_component, get_test_home_assistant

NAME = "foo"

MOCK_DATA = (
    '{"software": {"softwareVersion":"initial",'
    '"updateNewVersion":"initial"},'
    '"system": {"uptime":86400},'
    '"wan": {"localIpAddress":"initial", "online":true,'
    '"ipAddress":true}}'
)

MOCK_DATA_NEXT = (
    '{"software": {"softwareVersion":"next",'
    '"updateNewVersion":"0.0.0.0"},'
    '"system": {"uptime":172800},'
    '"wan": {"localIpAddress":"next", "online":false,'
    '"ipAddress":false}}'
)

MOCK_DATA_MISSING = '{"software": {},' '"system": {},' '"wan": {}}'


class TestGoogleWifiSetup(unittest.TestCase):
    """Tests for setting up the Google Wifi sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        resource = f"http://{google_wifi.DEFAULT_HOST}{google_wifi.ENDPOINT}"
        mock_req.get(resource, status_code=200)
        assert setup_component(
            self.hass,
            "sensor",
            {"sensor": {"platform": "google_wifi", "monitored_conditions": ["uptime"]}},
        )
        assert_setup_component(1, "sensor")

    @requests_mock.Mocker()
    def test_setup_get(self, mock_req):
        """Test setup with full configuration."""
        resource = f"http://localhost{google_wifi.ENDPOINT}"
        mock_req.get(resource, status_code=200)
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": {
                    "platform": "google_wifi",
                    "host": "localhost",
                    "name": "Test Wifi",
                    "monitored_conditions": [
                        "current_version",
                        "new_version",
                        "uptime",
                        "last_restart",
                        "local_ip",
                        "status",
                    ],
                }
            },
        )
        assert_setup_component(6, "sensor")


class TestGoogleWifiSensor(unittest.TestCase):
    """Tests for Google Wifi sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        with requests_mock.Mocker() as mock_req:
            self.setup_api(MOCK_DATA, mock_req)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def setup_api(self, data, mock_req):
        """Set up API with fake data."""
        resource = f"http://localhost{google_wifi.ENDPOINT}"
        now = datetime(1970, month=1, day=1)
        with patch("homeassistant.util.dt.now", return_value=now):
            mock_req.get(resource, text=data, status_code=200)
            conditions = google_wifi.MONITORED_CONDITIONS.keys()
            self.api = google_wifi.GoogleWifiAPI("localhost", conditions)
        self.name = NAME
        self.sensor_dict = {}
        for condition, cond_list in google_wifi.MONITORED_CONDITIONS.items():
            sensor = google_wifi.GoogleWifiSensor(self.api, self.name, condition)
            name = f"{self.name}_{condition}"
            units = cond_list[1]
            icon = cond_list[2]
            self.sensor_dict[condition] = {
                "sensor": sensor,
                "name": name,
                "units": units,
                "icon": icon,
            }

    def fake_delay(self, ha_delay):
        """Fake delay to prevent update throttle."""
        hass_now = dt_util.utcnow()
        shifted_time = hass_now + timedelta(seconds=ha_delay)
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: shifted_time})

    def test_name(self):
        """Test the name."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]["sensor"]
            test_name = self.sensor_dict[name]["name"]
            assert test_name == sensor.name

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]["sensor"]
            assert self.sensor_dict[name]["units"] == sensor.unit_of_measurement

    def test_icon(self):
        """Test the icon."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]["sensor"]
            assert self.sensor_dict[name]["icon"] == sensor.icon

    @requests_mock.Mocker()
    def test_state(self, mock_req):
        """Test the initial state."""
        self.setup_api(MOCK_DATA, mock_req)
        now = datetime(1970, month=1, day=1)
        with patch("homeassistant.util.dt.now", return_value=now):
            for name in self.sensor_dict:
                sensor = self.sensor_dict[name]["sensor"]
                self.fake_delay(2)
                sensor.update()
                if name == google_wifi.ATTR_LAST_RESTART:
                    assert "1969-12-31 00:00:00" == sensor.state
                elif name == google_wifi.ATTR_UPTIME:
                    assert 1 == sensor.state
                elif name == google_wifi.ATTR_STATUS:
                    assert "Online" == sensor.state
                else:
                    assert "initial" == sensor.state

    @requests_mock.Mocker()
    def test_update_when_value_is_none(self, mock_req):
        """Test state gets updated to unknown when sensor returns no data."""
        self.setup_api(None, mock_req)
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]["sensor"]
            self.fake_delay(2)
            sensor.update()
            assert sensor.state is None

    @requests_mock.Mocker()
    def test_update_when_value_changed(self, mock_req):
        """Test state gets updated when sensor returns a new status."""
        self.setup_api(MOCK_DATA_NEXT, mock_req)
        now = datetime(1970, month=1, day=1)
        with patch("homeassistant.util.dt.now", return_value=now):
            for name in self.sensor_dict:
                sensor = self.sensor_dict[name]["sensor"]
                self.fake_delay(2)
                sensor.update()
                if name == google_wifi.ATTR_LAST_RESTART:
                    assert "1969-12-30 00:00:00" == sensor.state
                elif name == google_wifi.ATTR_UPTIME:
                    assert 2 == sensor.state
                elif name == google_wifi.ATTR_STATUS:
                    assert "Offline" == sensor.state
                elif name == google_wifi.ATTR_NEW_VERSION:
                    assert "Latest" == sensor.state
                elif name == google_wifi.ATTR_LOCAL_IP:
                    assert STATE_UNKNOWN == sensor.state
                else:
                    assert "next" == sensor.state

    @requests_mock.Mocker()
    def test_when_api_data_missing(self, mock_req):
        """Test state logs an error when data is missing."""
        self.setup_api(MOCK_DATA_MISSING, mock_req)
        now = datetime(1970, month=1, day=1)
        with patch("homeassistant.util.dt.now", return_value=now):
            for name in self.sensor_dict:
                sensor = self.sensor_dict[name]["sensor"]
                self.fake_delay(2)
                sensor.update()
                assert STATE_UNKNOWN == sensor.state

    def test_update_when_unavailable(self):
        """Test state updates when Google Wifi unavailable."""
        self.api.update = Mock(
            "google_wifi.GoogleWifiAPI.update", side_effect=self.update_side_effect()
        )
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]["sensor"]
            sensor.update()
            assert sensor.state is None

    def update_side_effect(self):
        """Mock representation of update function."""
        self.api.data = None
        self.api.available = False
