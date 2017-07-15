"""The tests for the Google Wifi platform."""
import unittest
from unittest.mock import patch, Mock
from datetime import datetime
import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.sensor.google_wifi as google_wifi
from homeassistant.const import STATE_UNKNOWN

from tests.common import get_test_home_assistant, assert_setup_component

NAME = 'foo'

MOCK_DATA = ('{"software": {"softwareVersion":"initial",'
             '"updateNewVersion":"initial"},'
             '"system": {"uptime":86400},'
             '"wan": {"localIpAddress":"initial", "online":true,'
             '"ipAddress":true}}')

MOCK_DATA_NEXT = ('{"software": {"softwareVersion":"next",'
                  '"updateNewVersion":"0.0.0.0"},'
                  '"system": {"uptime":172800},'
                  '"wan": {"localIpAddress":"next", "online":false,'
                  '"ipAddress":false}}')


class TestGoogleWifiSetup(unittest.TestCase):
    """Tests for setting up the Google Wifi switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        resource = '{}{}{}'.format('http://',
                                   google_wifi.DEFAULT_HOST,
                                   google_wifi.ENDPOINT)
        mock_req.get(resource, status_code=200)
        self.assertTrue(setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'google_wifi'
            }
        }))

    @requests_mock.Mocker()
    def test_setup_get(self, mock_req):
        """Test setup with full configuration."""
        resource = '{}{}{}'.format('http://',
                                   'localhost',
                                   google_wifi.ENDPOINT)
        mock_req.get(resource, status_code=200)
        self.assertTrue(setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'google_wifi',
                'host': 'localhost',
                'name': 'Test Wifi',
                'monitored_conditions': ['current_version',
                                         'new_version',
                                         'uptime',
                                         'last_restart',
                                         'local_ip',
                                         'status']
            }
        }))
        assert_setup_component(6, 'sensor')


class TestGoogleWifiSensor(unittest.TestCase):
    """Tests for Google Wifi sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        resource = '{}{}{}'.format('http://',
                                   'localhost',
                                   google_wifi.ENDPOINT)
        with requests_mock.Mocker() as mock_req:
            mock_req.get(resource, text=MOCK_DATA, status_code=200)
            self.api = google_wifi.GoogleWifiAPI("localhost")
        self.name = NAME
        self.sensor_dict = dict()
        for condition, cond_list in google_wifi.MONITORED_CONDITIONS.items():
            sensor = google_wifi.GoogleWifiSensor(self.hass, self.api,
                                                  self.name, condition)
            name = '{}_{}'.format(self.name, condition)
            units = cond_list[1]
            icon = cond_list[2]
            self.sensor_dict[name] = {'sensor': sensor,
                                      'units': units,
                                      'icon': icon}

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]['sensor']
            self.assertEqual(name, sensor.name)

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]['sensor']
            self.assertEqual(self.sensor_dict[name]['units'],
                             sensor.unit_of_measurement)

    def test_icon(self):
        """Test the icon."""
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]['sensor']
            self.assertEqual(self.sensor_dict[name]['icon'], sensor.icon)

    @requests_mock.Mocker()
    def test_state(self, mock_req):
        """Test the initial state."""
        resource = '{}{}{}'.format('http://',
                                   'localhost',
                                   google_wifi.ENDPOINT)
        mock_req.get(resource, text=MOCK_DATA, status_code=200)
        now = datetime(1970, month=1, day=1)
        with patch('homeassistant.util.dt.now', return_value=now):
            for name in self.sensor_dict:
                sensor = self.sensor_dict[name]['sensor']
                sensor.update()
                if name == '{}_{}'.format(self.name,
                                          google_wifi.ATTR_LAST_RESTART):
                    self.assertEqual('1969-12-31 00:00:00', sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_UPTIME):
                    self.assertEqual(1, sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_STATUS):
                    self.assertEqual('Online', sensor.state)
                else:
                    self.assertEqual('initial', sensor.state)

    @requests_mock.Mocker()
    def test_update_when_value_is_none(self, mock_req):
        """Test state gets updated to unknown when sensor returns no data."""
        resource = '{}{}{}'.format('http://',
                                   'localhost',
                                   google_wifi.ENDPOINT)
        mock_req.get(resource, text=None, status_code=200)
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]['sensor']
            sensor.update()
            self.assertEqual(STATE_UNKNOWN, sensor.state)

    @requests_mock.Mocker()
    def test_update_when_value_changed(self, mock_req):
        """Test state gets updated when sensor returns a new status."""
        resource = '{}{}{}'.format('http://',
                                   'localhost',
                                   google_wifi.ENDPOINT)
        mock_req.get(resource, text=MOCK_DATA_NEXT, status_code=200)
        now = datetime(1970, month=1, day=1)
        with patch('homeassistant.util.dt.now', return_value=now):
            for name in self.sensor_dict:
                sensor = self.sensor_dict[name]['sensor']
                sensor.update()
                if name == '{}_{}'.format(self.name,
                                          google_wifi.ATTR_LAST_RESTART):
                    self.assertEqual('1969-12-30 00:00:00', sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_UPTIME):
                    self.assertEqual(2, sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_STATUS):
                    self.assertEqual('Offline', sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_NEW_VERSION):
                    self.assertEqual('Latest', sensor.state)
                elif name == '{}_{}'.format(self.name,
                                            google_wifi.ATTR_LOCAL_IP):
                    self.assertEqual(STATE_UNKNOWN, sensor.state)
                else:
                    self.assertEqual('next', sensor.state)

    def test_update_when_unavailiable(self):
        """Test state updates when Google Wifi unavailiable."""
        self.api.update = Mock('google_wifi.GoogleWifiAPI.update',
                               side_effect=self.update_side_effect())
        for name in self.sensor_dict:
            sensor = self.sensor_dict[name]['sensor']
            sensor.update()
            self.assertEqual(STATE_UNKNOWN, sensor.state)

    def update_side_effect(self):
        """Mock representation of update function."""
        self.api.data = None
        self.api.availiable = False
