"""The tests for the REST switch platform."""
import unittest
from unittest.mock import patch

import pytest
import requests
from requests.exceptions import Timeout
import requests_mock

import homeassistant.components.switch.rest as rest
from homeassistant.bootstrap import setup_component
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
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest'
        }, None))

    def test_setup_missing_schema(self):
        """Test setup with resource missing schema."""
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest',
            'resource': 'localhost'
        }, None))

    @patch('requests.get', side_effect=requests.exceptions.ConnectionError())
    def test_setup_failed_connect(self, mock_req):
        """Test setup when connection error occurs."""
        self.assertFalse(rest.setup_platform(self.hass, {
            'platform': 'rest',
            'resource': 'http://localhost',
        }, None))

    @patch('requests.get', side_effect=Timeout())
    def test_setup_timeout(self, mock_req):
        """Test setup when connection timeout occurs."""
        with self.assertRaises(Timeout):
            rest.setup_platform(self.hass, {
                'platform': 'rest',
                'resource': 'http://localhost',
            }, None)

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        mock_req.get('http://localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'rest',
                'resource': 'http://localhost'
            }
        }))
        self.assertEqual(1, mock_req.call_count)
        assert_setup_component(1, 'switch')

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.get('localhost', status_code=200)
        self.assertTrue(setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'rest',
                'name': 'foo',
                'resource': 'http://localhost',
                'body_on': 'custom on text',
                'body_off': 'custom off text',
            }
        }))
        self.assertEqual(1, mock_req.call_count)
        assert_setup_component(1, 'switch')


@pytest.mark.skip
class TestRestSwitch(unittest.TestCase):
    """Tests for REST switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.name = 'foo'
        self.resource = 'http://localhost/'
        self.body_on = 'on'
        self.body_off = 'off'
        self.switch = rest.RestSwitch(self.hass, self.name, self.resource,
                                      self.body_on, self.body_off)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        self.assertEqual(self.name, self.switch.name)

    def test_is_on_before_update(self):
        """Test is_on in initial state."""
        self.assertEqual(None, self.switch.is_on)

    @requests_mock.Mocker()
    def test_turn_on_success(self, mock_req):
        """Test turn_on."""
        mock_req.post(self.resource, status_code=200)
        self.switch.turn_on()

        self.assertEqual(self.body_on, mock_req.last_request.text)
        self.assertEqual(True, self.switch.is_on)

    @requests_mock.Mocker()
    def test_turn_on_status_not_ok(self, mock_req):
        """Test turn_on when error status returned."""
        mock_req.post(self.resource, status_code=500)
        self.switch.turn_on()

        self.assertEqual(self.body_on, mock_req.last_request.text)
        self.assertEqual(None, self.switch.is_on)

    @patch('requests.post', side_effect=Timeout())
    def test_turn_on_timeout(self, mock_req):
        """Test turn_on when timeout occurs."""
        with self.assertRaises(Timeout):
            self.switch.turn_on()

    @requests_mock.Mocker()
    def test_turn_off_success(self, mock_req):
        """Test turn_off."""
        mock_req.post(self.resource, status_code=200)
        self.switch.turn_off()

        self.assertEqual(self.body_off, mock_req.last_request.text)
        self.assertEqual(False, self.switch.is_on)

    @requests_mock.Mocker()
    def test_turn_off_status_not_ok(self, mock_req):
        """Test turn_off when error status returned."""
        mock_req.post(self.resource, status_code=500)
        self.switch.turn_off()

        self.assertEqual(self.body_off, mock_req.last_request.text)
        self.assertEqual(None, self.switch.is_on)

    @patch('requests.post', side_effect=Timeout())
    def test_turn_off_timeout(self, mock_req):
        """Test turn_off when timeout occurs."""
        with self.assertRaises(Timeout):
            self.switch.turn_on()

    @requests_mock.Mocker()
    def test_update_when_on(self, mock_req):
        """Test update when switch is on."""
        mock_req.get(self.resource, text=self.body_on)
        self.switch.update()

        self.assertEqual(True, self.switch.is_on)

    @requests_mock.Mocker()
    def test_update_when_off(self, mock_req):
        """Test update when switch is off."""
        mock_req.get(self.resource, text=self.body_off)
        self.switch.update()

        self.assertEqual(False, self.switch.is_on)

    @requests_mock.Mocker()
    def test_update_when_unknown(self, mock_req):
        """Test update when unknown status returned."""
        mock_req.get(self.resource, text='unknown status')
        self.switch.update()

        self.assertEqual(None, self.switch.is_on)

    @patch('requests.get', side_effect=Timeout())
    def test_update_timeout(self, mock_req):
        """Test update when timeout occurs."""
        with self.assertRaises(Timeout):
            self.switch.update()
