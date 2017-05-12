"""The tests for the REST switch platform."""
import unittest
from unittest.mock import patch, Mock

import requests
from requests.exceptions import Timeout, MissingSchema, RequestException
import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.sensor as sensor
import homeassistant.components.sensor.rest as rest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.config_validation import template

from tests.common import get_test_home_assistant, assert_setup_component


class TestRestSwitchSetup(unittest.TestCase):
    """Tests for setting up the REST switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(self.hass, sensor.DOMAIN, {
                'sensor': {'platform': 'rest'}})

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
        }, None))

    @patch('requests.Session.send', side_effect=Timeout())
    def test_setup_timeout(self, mock_req):
        """Test setup when connection timeout occurs."""
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest',
            'resource': 'http://localhost',
        }, None))

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        mock_req.get('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'sensor', {
            'sensor': {
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
        self.assertTrue(setup_component(self.hass, 'sensor', {
            'sensor': {
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
        assert_setup_component(1, 'sensor')

    @requests_mock.Mocker()
    def test_setup_post(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.post('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'sensor', {
            'sensor': {
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
        assert_setup_component(1, 'sensor')


class TestRestSensor(unittest.TestCase):
    """Tests for REST sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.initial_state = 'initial_state'
        self.rest = Mock('rest.RestData')
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(
                                    '{ "key": "' + self.initial_state + '" }'))
        self.name = 'foo'
        self.unit_of_measurement = 'MB'
        self.value_template = template('{{ value_json.key }}')
        self.value_template.hass = self.hass

        self.sensor = rest.RestSensor(self.hass, self.rest, self.name,
                                      self.unit_of_measurement,
                                      self.value_template)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def update_side_effect(self, data):
        """Side effect function for mocking RestData.update()."""
        self.rest.data = data

    def test_name(self):
        """Test the name."""
        self.assertEqual(self.name, self.sensor.name)

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        self.assertEqual(self.unit_of_measurement,
                         self.sensor.unit_of_measurement)

    def test_state(self):
        """Test the initial state."""
        self.assertEqual(self.initial_state, self.sensor.state)

    def test_update_when_value_is_none(self):
        """Test state gets updated to unknown when sensor returns no data."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(None))
        self.sensor.update()
        self.assertEqual(STATE_UNKNOWN, self.sensor.state)

    def test_update_when_value_changed(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(
                                    '{ "key": "updated_state" }'))
        self.sensor.update()
        self.assertEqual('updated_state', self.sensor.state)

    def test_update_with_no_template(self):
        """Test update when there is no value template."""
        self.rest.update = Mock('rest.RestData.update',
                                side_effect=self.update_side_effect(
                                    'plain_state'))
        self.sensor = rest.RestSensor(self.hass, self.rest, self.name,
                                      self.unit_of_measurement, None)
        self.sensor.update()
        self.assertEqual('plain_state', self.sensor.state)


class TestRestData(unittest.TestCase):
    """Tests for RestData."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.method = "GET"
        self.resource = "http://localhost"
        self.verify_ssl = True
        self.rest = rest.RestData(self.method, self.resource, None, None, None,
                                  self.verify_ssl)

    @requests_mock.Mocker()
    def test_update(self, mock_req):
        """Test update."""
        mock_req.get('http://localhost', text='test data')
        self.rest.update()
        self.assertEqual('test data', self.rest.data)

    @patch('requests.Session', side_effect=RequestException)
    def test_update_request_exception(self, mock_req):
        """Test update when a request exception occurs."""
        self.rest.update()
        self.assertEqual(None, self.rest.data)
