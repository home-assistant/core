"""The tests for the REST sensor platform."""
from os import path
import unittest

import pytest
from pytest import raises
import requests
from requests.exceptions import RequestException, Timeout
from requests.structures import CaseInsensitiveDict
import requests_mock

from homeassistant import config as hass_config
import homeassistant.components.rest.sensor as rest
import homeassistant.components.sensor as sensor
from homeassistant.const import DATA_MEGABYTES, SERVICE_RELOAD
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.config_validation import template
from homeassistant.setup import async_setup_component, setup_component

from tests.async_mock import Mock, patch
from tests.common import assert_setup_component, get_test_home_assistant


class TestRestSensorSetup(unittest.TestCase):
    """Tests for setting up the REST sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

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
            self.hass.block_till_done()
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
            self.hass.block_till_done()
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
            self.hass.block_till_done()

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
                        "unit_of_measurement": DATA_MEGABYTES,
                        "verify_ssl": "true",
                        "timeout": 30,
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
            self.hass.block_till_done()
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
                        "unit_of_measurement": DATA_MEGABYTES,
                        "verify_ssl": "true",
                        "timeout": 30,
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "application/json"},
                    }
                },
            )
            self.hass.block_till_done()
        assert 2 == mock_req.call_count

    @requests_mock.Mocker()
    def test_setup_get_xml(self, mock_req):
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
                        "unit_of_measurement": DATA_MEGABYTES,
                        "verify_ssl": "true",
                        "timeout": 30,
                        "authentication": "basic",
                        "username": "my username",
                        "password": "my password",
                        "headers": {"Accept": "text/xml"},
                    }
                },
            )
            self.hass.block_till_done()
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
                '{ "key": "' + self.initial_state + '" }',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
        )
        self.name = "foo"
        self.unit_of_measurement = DATA_MEGABYTES
        self.device_class = None
        self.value_template = template("{{ value_json.key }}")
        self.json_attrs_path = None
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
            self.json_attrs_path,
        )
        self.addCleanup(self.hass.stop)

    def update_side_effect(self, data, headers):
        """Side effect function for mocking RestData.update()."""
        self.rest.data = data
        self.rest.headers = headers

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
            "rest.RestData.update",
            side_effect=self.update_side_effect(None, CaseInsensitiveDict()),
        )
        self.sensor.update()
        assert self.sensor.state is None
        assert not self.sensor.available

    def test_update_when_value_changed(self):
        """Test state gets updated when sensor returns a new status."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '{ "key": "updated_state" }',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
        )
        self.sensor.update()
        assert "updated_state" == self.sensor.state
        assert self.sensor.available

    def test_update_with_no_template(self):
        """Test update when there is no value template."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                "plain_state", CaseInsensitiveDict({"Content-Type": "application/json"})
            ),
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
            self.json_attrs_path,
        )
        self.sensor.update()
        assert "plain_state" == self.sensor.state
        assert self.sensor.available

    def test_update_with_json_attrs(self):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '{ "key": "some_json_value" }',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
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
            self.json_attrs_path,
        )
        self.sensor.update()
        assert "some_json_value" == self.sensor.device_state_attributes["key"]

    def test_update_with_json_attrs_list_dict(self):
        """Test attributes get extracted from a JSON list[0] result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '[{ "key": "another_value" }]',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
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
            self.json_attrs_path,
        )
        self.sensor.update()
        assert "another_value" == self.sensor.device_state_attributes["key"]

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_no_data(self, mock_logger):
        """Test attributes when no JSON result fetched."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                None, CaseInsensitiveDict({"Content-Type": "application/json"})
            ),
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
            self.json_attrs_path,
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_not_dict(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '["list", "of", "things"]',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
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
            self.json_attrs_path,
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_json_attrs_bad_JSON(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                "This is text rather than JSON data.",
                CaseInsensitiveDict({"Content-Type": "text/plain"}),
            ),
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
            self.json_attrs_path,
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
                '{ "key": "json_state_updated_value" }',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
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
            self.json_attrs_path,
        )
        self.sensor.update()

        assert "json_state_updated_value" == self.sensor.state
        assert (
            "json_state_updated_value" == self.sensor.device_state_attributes["key"]
        ), self.force_update

    def test_update_with_json_attrs_with_json_attrs_path(self):
        """Test attributes get extracted from a JSON result with a template for the attributes."""
        json_attrs_path = "$.toplevel.second_level"
        value_template = template("{{ value_json.toplevel.master_value }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '{ "toplevel": {"master_value": "master", "second_level": {"some_json_key": "some_json_value", "some_json_key2": "some_json_value2" } } }',
                CaseInsensitiveDict({"Content-Type": "application/json"}),
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["some_json_key", "some_json_key2"],
            self.force_update,
            self.resource_template,
            json_attrs_path,
        )

        self.sensor.update()
        assert "some_json_value" == self.sensor.device_state_attributes["some_json_key"]
        assert (
            "some_json_value2" == self.sensor.device_state_attributes["some_json_key2"]
        )
        assert "master" == self.sensor.state

    def test_update_with_xml_convert_json_attrs_with_json_attrs_path(self):
        """Test attributes get extracted from a JSON result that was converted from XML with a template for the attributes."""
        json_attrs_path = "$.toplevel.second_level"
        value_template = template("{{ value_json.toplevel.master_value }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                "<toplevel><master_value>master</master_value><second_level><some_json_key>some_json_value</some_json_key><some_json_key2>some_json_value2</some_json_key2></second_level></toplevel>",
                CaseInsensitiveDict({"Content-Type": "text/xml+svg"}),
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["some_json_key", "some_json_key2"],
            self.force_update,
            self.resource_template,
            json_attrs_path,
        )

        self.sensor.update()
        assert "some_json_value" == self.sensor.device_state_attributes["some_json_key"]
        assert (
            "some_json_value2" == self.sensor.device_state_attributes["some_json_key2"]
        )
        assert "master" == self.sensor.state

    def test_update_with_xml_convert_json_attrs_with_jsonattr_template(self):
        """Test attributes get extracted from a JSON result that was converted from XML."""
        json_attrs_path = "$.response"
        value_template = template("{{ value_json.response.bss.wlan }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                '<?xml version="1.0" encoding="utf-8"?><response><scan>0</scan><ver>12556</ver><count>48</count><ssid>alexander</ssid><bss><valid>0</valid><name>0</name><privacy>0</privacy><wlan>bogus</wlan><strength>0</strength></bss><led0>0</led0><led1>0</led1><led2>0</led2><led3>0</led3><led4>0</led4><led5>0</led5><led6>0</led6><led7>0</led7><btn0>up</btn0><btn1>up</btn1><btn2>up</btn2><btn3>up</btn3><pot0>0</pot0><usr0>0</usr0><temp0>0x0XF0x0XF</temp0><time0> 0</time0></response>',
                CaseInsensitiveDict({"Content-Type": "text/xml"}),
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["led0", "led1", "temp0", "time0", "ver"],
            self.force_update,
            self.resource_template,
            json_attrs_path,
        )

        self.sensor.update()
        assert "0" == self.sensor.device_state_attributes["led0"]
        assert "0" == self.sensor.device_state_attributes["led1"]
        assert "0x0XF0x0XF" == self.sensor.device_state_attributes["temp0"]
        assert "0" == self.sensor.device_state_attributes["time0"]
        assert "12556" == self.sensor.device_state_attributes["ver"]
        assert "bogus" == self.sensor.state

    def test_update_with_application_xml_convert_json_attrs_with_jsonattr_template(
        self,
    ):
        """Test attributes get extracted from a JSON result that was converted from XML with application/xml mime type."""
        json_attrs_path = "$.main"
        value_template = template("{{ value_json.main.dog }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                "<main><dog>1</dog><cat>3</cat></main>",
                CaseInsensitiveDict({"Content-Type": "application/xml"}),
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["dog", "cat"],
            self.force_update,
            self.resource_template,
            json_attrs_path,
        )

        self.sensor.update()
        assert "3" == self.sensor.device_state_attributes["cat"]
        assert "1" == self.sensor.device_state_attributes["dog"]
        assert "1" == self.sensor.state

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_xml_convert_bad_xml(self, mock_logger):
        """Test attributes get extracted from a XML result with bad xml."""
        value_template = template("{{ value_json.toplevel.master_value }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(
                "this is not xml", CaseInsensitiveDict({"Content-Type": "text/xml"})
            ),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["key"],
            self.force_update,
            self.resource_template,
            self.json_attrs_path,
        )

        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called
        assert mock_logger.debug.called

    @patch("homeassistant.components.rest.sensor._LOGGER")
    def test_update_with_failed_get(self, mock_logger):
        """Test attributes get extracted from a XML result with bad xml."""
        value_template = template("{{ value_json.toplevel.master_value }}")
        value_template.hass = self.hass

        self.rest.update = Mock(
            "rest.RestData.update",
            side_effect=self.update_side_effect(None, None),
        )
        self.sensor = rest.RestSensor(
            self.hass,
            self.rest,
            self.name,
            self.unit_of_measurement,
            self.device_class,
            value_template,
            ["key"],
            self.force_update,
            self.resource_template,
            self.json_attrs_path,
        )

        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called
        assert mock_logger.debug.called
        assert self.sensor.state is None
        assert self.sensor.available is False


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

    @patch("requests.Session.request", side_effect=RequestException)
    def test_update_request_exception(self, mock_req):
        """Test update when a request exception occurs."""
        self.rest.update()
        assert self.rest.data is None


async def test_reload(hass, requests_mock):
    """Verify we can reload reset sensors."""

    requests_mock.get("http://localhost", text="test data")

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rest",
                "method": "GET",
                "name": "mockrest",
                "resource": "http://localhost",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.mockrest")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "rest/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "rest",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.mockreset") is None
    assert hass.states.get("sensor.rollout")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
