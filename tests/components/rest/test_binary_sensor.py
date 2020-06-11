"""The tests for the REST binary sensor platform."""
import unittest

import pytest
from pytest import raises
import requests
from requests.exceptions import Timeout
import requests_mock

import homeassistant.components.binary_sensor as binary_sensor
import homeassistant.components.rest.binary_sensor as rest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import template
from homeassistant.setup import setup_component

from tests.async_mock import Mock, patch
from tests.common import assert_setup_component, get_test_home_assistant


class TestRestBinarySensorSetup(unittest.TestCase):
    """Tests for setting up the REST binary sensor platform."""

    DEVICES = []

    def add_devices(self, devices, update_before_add=False):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        # Reset for this test.
        self.DEVICES = []
        self.addCleanup(self.hass.stop)

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass, binary_sensor.DOMAIN, {"binary_sensor": {"platform": "rest"}}
            )

    def test_setup_missing_schema(self):
        """Test setup with resource missing schema."""
        with pytest.raises(PlatformNotReady):
            rest.setup_platform(
                self.hass,
                {"platform": "rest", "resource": "localhost", "method": "GET"},
                None,
            )

    @patch("requests.Session.send", side_effect=requests.exceptions.ConnectionError())
    def test_setup_failed_connect(self, mock_req):
        """Test setup when connection error occurs."""
        with raises(PlatformNotReady):
            rest.setup_platform(
                self.hass,
                {"platform": "rest", "resource": "http://localhost", "method": "GET"},
                self.add_devices,
                None,
            )
        assert len(self.DEVICES) == 0

    @patch("requests.Session.send", side_effect=Timeout())
    def test_setup_timeout(self, mock_req):
        """Test setup when connection timeout occurs."""
        with raises(PlatformNotReady):
            rest.setup_platform(
                self.hass,
                {"platform": "rest", "resource": "http://localhost", "method": "GET"},
                self.add_devices,
                None,
            )
        assert len(self.DEVICES) == 0

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(1, "binary_sensor"):
            assert setup_component(
                self.hass,
                "binary_sensor",
                {"binary_sensor": {"platform": "rest", "resource": "http://localhost"}},
            )
            self.hass.block_till_done()
        assert 1 == mock_req.call_count

    @requests_mock.Mocker()
    def test_setup_get(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(1, "binary_sensor"):
            assert setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "rest",
                        "resource": "http://localhost",
                        "method": "GET",
                        "value_template": "{{ value_json.key }}",
                        "name": "foo",
                        "verify_ssl": "true",
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
            self.hass.block_till_done()
        assert 1 == mock_req.call_count

    @requests_mock.Mocker()
    def test_setup_post(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.post("http://localhost", status_code=200)
        with assert_setup_component(1, "binary_sensor"):
            assert setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "rest",
                        "resource": "http://localhost",
                        "method": "POST",
                        "value_template": "{{ value_json.key }}",
                        "payload": '{ "device": "toaster"}',
                        "name": "foo",
                        "verify_ssl": "true",
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
            self.hass.block_till_done()
        assert 1 == mock_req.call_count


class TestRestBinarySensor(unittest.TestCase):
    """Tests for REST binary sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.rest = Mock("RestData")
        self.rest.update = Mock(
            "RestData.update", side_effect=self.update_side_effect('{ "key": false }')
        )
        self.name = "foo"
        self.device_class = "light"
        self.value_template = template.Template("{{ value_json.key }}", self.hass)

        self.binary_sensor = rest.RestBinarySensor(
            self.hass, self.rest, self.name, self.device_class, self.value_template
        )
        self.addCleanup(self.hass.stop)

    def update_side_effect(self, data):
        """Side effect function for mocking RestData.update()."""
        self.rest.data = data

    def test_name(self):
        """Test the name."""
        assert self.name == self.binary_sensor.name

    def test_device_class(self):
        """Test the device class."""
        assert self.device_class == self.binary_sensor.device_class

    def test_initial_state(self):
        """Test the initial state."""
        self.binary_sensor.update()
        assert STATE_OFF == self.binary_sensor.state

    def test_update_when_value_is_none(self):
        """Test state gets updated to unknown when sensor returns no data."""
        self.rest.update = Mock(
            "RestData.update", side_effect=self.update_side_effect(None)
        )
        self.binary_sensor.update()
        assert not self.binary_sensor.available

    def test_update_when_value_changed(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect('{ "key": true }'),
        )
        self.binary_sensor.update()
        assert STATE_ON == self.binary_sensor.state
        assert self.binary_sensor.available

    def test_update_when_failed_request(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock(
            "rest.RestData.update", side_effect=self.update_side_effect(None)
        )
        self.binary_sensor.update()
        assert not self.binary_sensor.available

    def test_update_with_no_template(self):
        """Test update when there is no value template."""
        self.rest.update = Mock(
            "rest.RestData.update", side_effect=self.update_side_effect("true")
        )
        self.binary_sensor = rest.RestBinarySensor(
            self.hass, self.rest, self.name, self.device_class, None
        )
        self.binary_sensor.update()
        assert STATE_ON == self.binary_sensor.state
        assert self.binary_sensor.available
