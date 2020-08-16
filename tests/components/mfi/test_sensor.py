"""The tests for the mFi sensor platform."""
import unittest

from mficlient.client import FailedToLogin
import requests

import homeassistant.components.mfi.sensor as mfi
import homeassistant.components.sensor as sensor
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import setup_component

import tests.async_mock as mock
from tests.common import get_test_home_assistant


class TestMfiSensorSetup(unittest.TestCase):
    """Test the mFi sensor platform."""

    PLATFORM = mfi
    COMPONENT = sensor
    THING = "sensor"
    GOOD_CONFIG = {
        "sensor": {
            "platform": "mfi",
            "host": "foo",
            "port": 6123,
            "username": "user",
            "password": "pass",
            "ssl": True,
            "verify_ssl": True,
        }
    }

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_missing_config(self, mock_client):
        """Test setup with missing configuration."""
        config = {"sensor": {"platform": "mfi"}}
        assert setup_component(self.hass, "sensor", config)
        assert not mock_client.called

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_failed_login(self, mock_client):
        """Test setup with login failure."""
        mock_client.side_effect = FailedToLogin
        assert not self.PLATFORM.setup_platform(self.hass, dict(self.GOOD_CONFIG), None)

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_failed_connect(self, mock_client):
        """Test setup with connection failure."""
        mock_client.side_effect = requests.exceptions.ConnectionError
        assert not self.PLATFORM.setup_platform(self.hass, dict(self.GOOD_CONFIG), None)

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_minimum(self, mock_client):
        """Test setup with minimum configuration."""
        config = dict(self.GOOD_CONFIG)
        del config[self.THING]["port"]
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        self.hass.block_till_done()
        assert mock_client.call_count == 1
        assert mock_client.call_args == mock.call(
            "foo", "user", "pass", port=6443, use_tls=True, verify=True
        )

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_with_port(self, mock_client):
        """Test setup with port."""
        config = dict(self.GOOD_CONFIG)
        config[self.THING]["port"] = 6123
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        self.hass.block_till_done()
        assert mock_client.call_count == 1
        assert mock_client.call_args == mock.call(
            "foo", "user", "pass", port=6123, use_tls=True, verify=True
        )

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    def test_setup_with_tls_disabled(self, mock_client):
        """Test setup without TLS."""
        config = dict(self.GOOD_CONFIG)
        del config[self.THING]["port"]
        config[self.THING]["ssl"] = False
        config[self.THING]["verify_ssl"] = False
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        self.hass.block_till_done()
        assert mock_client.call_count == 1
        assert mock_client.call_args == mock.call(
            "foo", "user", "pass", port=6080, use_tls=False, verify=False
        )

    @mock.patch("homeassistant.components.mfi.sensor.MFiClient")
    @mock.patch("homeassistant.components.mfi.sensor.MfiSensor")
    def test_setup_adds_proper_devices(self, mock_sensor, mock_client):
        """Test if setup adds devices."""
        ports = {
            i: mock.MagicMock(model=model) for i, model in enumerate(mfi.SENSOR_MODELS)
        }
        ports["bad"] = mock.MagicMock(model="notasensor")
        mock_client.return_value.get_devices.return_value = [
            mock.MagicMock(ports=ports)
        ]
        assert setup_component(self.hass, sensor.DOMAIN, self.GOOD_CONFIG)
        self.hass.block_till_done()
        for ident, port in ports.items():
            if ident != "bad":
                mock_sensor.assert_any_call(port, self.hass)
        assert mock.call(ports["bad"], self.hass) not in mock_sensor.mock_calls


class TestMfiSensor(unittest.TestCase):
    """Test for mFi sensor platform."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.port = mock.MagicMock()
        self.sensor = mfi.MfiSensor(self.port, self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        assert self.port.label == self.sensor.name

    def test_uom_temp(self):
        """Test the UOM temperature."""
        self.port.tag = "temperature"
        assert TEMP_CELSIUS == self.sensor.unit_of_measurement

    def test_uom_power(self):
        """Test the UOEM power."""
        self.port.tag = "active_pwr"
        assert "Watts" == self.sensor.unit_of_measurement

    def test_uom_digital(self):
        """Test the UOM digital input."""
        self.port.model = "Input Digital"
        assert "State" == self.sensor.unit_of_measurement

    def test_uom_unknown(self):
        """Test the UOM."""
        self.port.tag = "balloons"
        assert "balloons" == self.sensor.unit_of_measurement

    def test_uom_uninitialized(self):
        """Test that the UOM defaults if not initialized."""
        type(self.port).tag = mock.PropertyMock(side_effect=ValueError)
        assert "State" == self.sensor.unit_of_measurement

    def test_state_digital(self):
        """Test the digital input."""
        self.port.model = "Input Digital"
        self.port.value = 0
        assert mfi.STATE_OFF == self.sensor.state
        self.port.value = 1
        assert mfi.STATE_ON == self.sensor.state
        self.port.value = 2
        assert mfi.STATE_ON == self.sensor.state

    def test_state_digits(self):
        """Test the state of digits."""
        self.port.tag = "didyoucheckthedict?"
        self.port.value = 1.25
        with mock.patch.dict(mfi.DIGITS, {"didyoucheckthedict?": 1}):
            assert 1.2 == self.sensor.state
        with mock.patch.dict(mfi.DIGITS, {}):
            assert 1.0 == self.sensor.state

    def test_state_uninitialized(self):
        """Test the state of uninitialized sensors."""
        type(self.port).tag = mock.PropertyMock(side_effect=ValueError)
        assert mfi.STATE_OFF == self.sensor.state

    def test_update(self):
        """Test the update."""
        self.sensor.update()
        assert self.port.refresh.call_count == 1
        assert self.port.refresh.call_args == mock.call()
