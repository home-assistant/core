"""The tests for the REST sensor platform."""
import unittest
from unittest.mock import Mock, patch

import pytest
from pytest import raises
import requests
from requests.exceptions import RequestException, Timeout
import requests_mock

import homeassistant.components.rest.sensor as rest
import homeassistant.components.sensor as sensor
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.config_validation import template
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestRestSensorSetup(unittest.TestCase):
    """Tests for setting up the REST sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass, sensor.DOMAIN, {"sensor": {"platform": "rest"}}
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
                lambda devices, update=True: None,
            )

    @patch("requests.Session.send", side_effect=Timeout())
    def test_setup_timeout(self, mock_req):
        """Test setup when connection timeout occurs."""
        with raises(PlatformNotReady):
            rest.setup_platform(
                self.hass,
                {"platform": "rest", "resource": "http://localhost", "method": "GET"},
                lambda devices, update=True: None,
            )

    @requests_mock.Mocker()
    def test_setup_minimum(self, mock_req):
        """Test setup with minimum configuration."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(1, "sensor"):
            assert setup_component(
                self.hass,
                "sensor",
                {"sensor": {"platform": "rest", "resource": "http://localhost"}},
            )
        assert 2 == mock_req.call_count

    @requests_mock.Mocker()
    def test_setup_minimum_resource_template(self, mock_req):
        """Test setup with minimum configuration (resource_template)."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(1, "sensor"):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "rest",
                        "resource_template": "http://localhost",
                    }
                },
            )
        assert mock_req.call_count == 2

    @requests_mock.Mocker()
    def test_setup_duplicate_resource(self, mock_req):
        """Test setup with duplicate resources."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(0, "sensor"):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "rest",
                        "resource": "http://localhost",
                        "resource_template": "http://localhost",
                    }
                },
            )

    @requests_mock.Mocker()
    def test_setup_get(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.get("http://localhost", status_code=200)
        with assert_setup_component(1, "sensor"):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "rest",
                        "resource": "http://localhost",
                        "method": "GET",
                        "value_template": "{{ value_json.key }}",
                        "name": "foo",
                        "unit_of_measurement": "MB",
                        "verify_ssl": "true",
                        "timeout": 30,
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
        assert 2 == mock_req.call_count

    @requests_mock.Mocker()
    def test_setup_post(self, mock_req):
        """Test setup with valid configuration."""
        mock_req.post("http://localhost", status_code=200)
        with assert_setup_component(1, "sensor"):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "rest",
                        "resource": "http://localhost",
                        "method": "POST",
                        "value_template": "{{ value_json.key }}",
                        "payload": '{ "device": "toaster"}',
                        "name": "foo",
                        "unit_of_measurement": "MB",
                        "verify_ssl": "true",
                        "timeout": 30,
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
        assert 2 == mock_req.call_count


class TestRestSensor(unittest.TestCase):
    """Tests for REST sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.initial_state = "initial_state"
        self.rest = Mock("rest.RestData")
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '{ "key": "' + self.initial_state + '" }'
            ),
        )
        self.name = "foo"
        self.unit_of_measurement = "MB"
        self.device_class = None
        self.value_template = template("{{ value_json.key }}")
        self.value_template.hass = self.hass
        self.force_update = False
        self.resource_template = None

        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            self.value_template,
            [],
            self.force_update,
            self.resource_template,
        )

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def update_side_effect(self, data):
        """Side effect function for mocking RestData.update()."""
        self.rest.data = data

    def test_name(self):
        """Test the name."""
        assert self.name == self.sensor.name

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        assert self.unit_of_measurement == self.sensor.unit_of_measurement

    def test_force_update(self):
        """Test the unit of measurement."""
        assert self.force_update == self.sensor.force_update

    def test_state(self):
        """Test the initial state."""
        self.sensor.update()
        assert self.initial_state == self.sensor.state

    def test_update_when_value_is_none(self):
        """Test state gets updated to unknown when sensor returns no data."""
        self.rest.update = Mock(
            "rest.RestData.update", side_effect=self.update_side_effect(None)
        )
        self.sensor.update()
        assert self.sensor.state is None
        assert not self.sensor.available

    def test_update_when_value_changed(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect('{ "key": "updated_state" }'),
        )
        self.sensor.update()
        assert "updated_state" == self.sensor.state
        assert self.sensor.available

    def test_update_with_no_template(self):
        """Test update when there is no value template."""
        self.rest.update = Mock(
            "rest.RestData.update", side_effect=self.update_side_effect("plain_state")
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            [],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert "plain_state" == self.sensor.state
        assert self.sensor.available

    def test_update_with_json_attrs(self):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect('{ "key": "some_json_value" }'),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert "some_json_value" == self.sensor.device_state_attributes["key"]

    def test_update_with_json_attrs_list_dict(self):
        """Test attributes get extracted from a JSON list[0] result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect('[{ "key": "another_value" }]'),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert "another_value" == self.sensor.device_state_attributes["key"]

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_no_data(self, mock_logger):
        """Test attributes when no JSON result fetched."""
        self.rest.update = Mock(
            "rest.RestData.update", side_effect=self.update_side_effect(None)
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_not_dict(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect('["list", "of", "things"]'),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_bad_JSON(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect("This is text rather than JSON data."),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            None,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called
        assert mock_logger.debug.called

    def test_update_with_json_attrs_and_template(self):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '{ "key": "json_state_updated_value" }'
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            self.value_template,
            ["key"],
            self.force_update,
            self.resource_template,
        )
        self.sensor.update()

        assert "json_state_updated_value" == self.sensor.state
        assert (
            "json_state_updated_value" == self.sensor.device_state_attributes["key"]
        ), self.force_update


class TestRestData(unittest.TestCase):
    """Tests for RestData."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.method = "GET"
        self.resource = "http://localhost"
        self.verify_ssl = True
        self.timeout = 10
        self.rest = rest.RestData(
            self.method, self.resource, None, None, None, self.verify_ssl, self.timeout
        )

    @requests_mock.Mocker()
    def test_update(self, mock_req):
        """Test update."""
        mock_req.get("http://localhost", text="test data")
        self.rest.update()
        assert "test data" == self.rest.data

    @patch("requests.request", side_effect=RequestException)
    def test_update_request_exception(self, mock_req):
        """Test update when a request exception occurs."""
        self.rest.update()
        assert self.rest.data is None
