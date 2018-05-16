"""The tests for the REST binary sensor platform."""
import unittest
from unittest.mock import patch, Mock

import requests
from requests.exceptions import Timeout, MissingSchema
import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.binary_sensor as binary_sensor
import homeassistant.components.binary_sensor.rest as rest
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers import template

from tests.common import get_test_home_assistant, assert_setup_component


class TestRestBinarySensorSetup(unittest.TestCase):
    """Tests for setting up the REST binary sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(self.hass, binary_sensor.DOMAIN, {
                'binary_sensor': {'platform': 'rest'}})

    def test_setup_missing_schema(self):
        """Test setup with resource missing schema."""
        with self.assertRaises(MissingSchema):
            rest.setup_platform(self.hass, {
                'platform': 'rest',
                'resource': 'localhost',
                'method': 'GET'
            }, None)

    @patch('requests.Session.send',
           side_effect=requests.exceptions.ConnectionError())
    def test_setup_failed_connect(self, mock_req):
        """Test setup when connection error occurs."""
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest',
            'resource': 'http://localhost',
        }, lambda devices, update=True: None))

    @patch('requests.Session.send', side_effect=Timeout())
    def test_setup_timeout(self, mock_req):
        """Test setup when connection timeout occurs."""
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest',
            'resource': 'http://localhost',
        }, lambda devices, update=True: None))

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        mock_req.get('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'rest',
                'resource': 'http://localhost'
            }
        }))
        self.assertEqual(2, mock_req.call_count)
        assert_setup_component(1, 'switch')

    @requests_mock.Mocker()
    def test_setup_get(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.get('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'rest',
                'resource': 'http://localhost',
                'method': 'GET',
                'value_template': '{{ value_json.key }}',
                'name': 'foo',
                'unit_of_measurement': 'MB',
                'verify_ssl': 'true',
                'authentication': 'basic',
                'username': 'my username',
                'password': 'my password',
                'headers': {'Accept': 'application/json'}
            }
        }))
        self.assertEqual(2, mock_req.call_count)
        assert_setup_component(1, 'binary_sensor')

    @requests_mock.Mocker()
    def test_setup_post(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.post('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'rest',
                'resource': 'http://localhost',
                'method': 'POST',
                'value_template': '{{ value_json.key }}',
                'payload': '{ "device": "toaster"}',
                'name': 'foo',
                'unit_of_measurement': 'MB',
                'verify_ssl': 'true',
                'authentication': 'basic',
                'username': 'my username',
                'password': 'my password',
                'headers': {'Accept': 'application/json'}
            }
        }))
        self.assertEqual(2, mock_req.call_count)
        assert_setup_component(1, 'binary_sensor')


class TestRestBinarySensor(unittest.TestCase):
    """Tests for REST binary sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.rest = Mock('RestData')
        self.rest.update = Mock('RestData.update',
                                side_effect=self.update_side_effect(
                                    '{ "key": false }'))
        self.name = 'foo'
        self.device_class = 'light'
        self.value_template = \
            template.Template('{{ value_json.key }}', self.hass)

        self.binary_sensor = rest.RestBinarySensor(
            self.hass, self.rest, self.name, self.device_class,
            self.value_template)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def update_side_effect(self, data):
        """Side effect function for mocking RestData.update()."""
        self.rest.data = data

    def test_name(self):
        """Test the name."""
        self.assertEqual(self.name, self.binary_sensor.name)

    def test_device_class(self):
        """Test the device class."""
        self.assertEqual(self.device_class, self.binary_sensor.device_class)

    def test_initial_state(self):
        """Test the initial state."""
        self.binary_sensor.update()
        self.assertEqual(STATE_OFF, self.binary_sensor.state)

    def test_update_when_value_is_none(self):
        """Test state gets updated to unknown when sensor returns no data."""
        self.rest.update = Mock(
            'RestData.update',
            side_effect=self.update_side_effect(None))
        self.binary_sensor.update()
        self.assertFalse(self.binary_sensor.available)

    def test_update_when_value_changed(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(
                                    '{ "key": true }'))
        self.binary_sensor.update()
        self.assertEqual(STATE_ON, self.binary_sensor.state)
        self.assertTrue(self.binary_sensor.available)

    def test_update_when_failed_request(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(None))
        self.binary_sensor.update()
        self.assertFalse(self.binary_sensor.available)

    def test_update_with_no_template(self):
        """Test update when there is no value template."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect('true'))
        self.binary_sensor = rest.RestBinarySensor(
            self.hass, self.rest, self.name, self.device_class, None)
        self.binary_sensor.update()
        self.assertEqual(STATE_ON, self.binary_sensor.state)
        self.assertTrue(self.binary_sensor.available)
