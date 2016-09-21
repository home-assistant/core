"""The tests for the mFi sensor platform."""
import unittest
import unittest.mock as mock

import requests

from homeassistant.bootstrap import setup_component
import homeassistant.components.sensor as sensor
import homeassistant.components.sensor.mfi as mfi
from homeassistant.const import TEMP_CELSIUS

from tests.common import get_test_home_assistant


class TestMfiSensorSetup(unittest.TestCase):
    """Test the mFi sensor platform."""

    PLATFORM = mfi
    COMPONENT = sensor
    THING = 'sensor'
    GOOD_CONFIG = {
        'sensor': {
            'platform': 'mfi',
            'host': 'foo',
            'port': 6123,
            'username': 'user',
            'password': 'pass',
            'ssl': True,
            'verify_ssl': True,
        }
    }

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with missing configuration."""
        config = {
            'sensor': {
                'platform': 'mfi',
            }
        }
        self.assertFalse(self.PLATFORM.setup_platform(self.hass, config, None))

    @mock.patch('mficlient.client')
    def test_setup_failed_login(self, mock_client):
        """Test setup with login failure."""
        mock_client.FailedToLogin = Exception()
        mock_client.MFiClient.side_effect = mock_client.FailedToLogin
        self.assertFalse(
            self.PLATFORM.setup_platform(
                self.hass, dict(self.GOOD_CONFIG), None))

    @mock.patch('mficlient.client')
    def test_setup_failed_connect(self, mock_client):
        """Test setup with conection failure."""
        mock_client.FailedToLogin = Exception()
        mock_client.MFiClient.side_effect = requests.exceptions.ConnectionError
        self.assertFalse(
            self.PLATFORM.setup_platform(
                self.hass, dict(self.GOOD_CONFIG), None))

    @mock.patch('mficlient.client.MFiClient')
    def test_setup_minimum(self, mock_client):
        """Test setup with minimum configuration."""
        config = dict(self.GOOD_CONFIG)
        del config[self.THING]['port']
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        mock_client.assert_called_once_with(
            'foo', 'user', 'pass', port=6443, use_tls=True, verify=True)

    @mock.patch('mficlient.client.MFiClient')
    def test_setup_with_port(self, mock_client):
        """Test setup with port."""
        config = dict(self.GOOD_CONFIG)
        config[self.THING]['port'] = 6123
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        mock_client.assert_called_once_with(
            'foo', 'user', 'pass', port=6123, use_tls=True, verify=True)

    @mock.patch('mficlient.client.MFiClient')
    def test_setup_with_tls_disabled(self, mock_client):
        """Test setup without TLS."""
        config = dict(self.GOOD_CONFIG)
        del config[self.THING]['port']
        config[self.THING]['ssl'] = False
        config[self.THING]['verify_ssl'] = False
        assert setup_component(self.hass, self.COMPONENT.DOMAIN, config)
        mock_client.assert_called_once_with(
            'foo', 'user', 'pass', port=6080, use_tls=False, verify=False)

    @mock.patch('mficlient.client.MFiClient')
    @mock.patch('homeassistant.components.sensor.mfi.MfiSensor')
    def test_setup_adds_proper_devices(self, mock_sensor, mock_client):
        """Test if setup adds devices."""
        ports = {i: mock.MagicMock(model=model)
                 for i, model in enumerate(mfi.SENSOR_MODELS)}
        ports['bad'] = mock.MagicMock(model='notasensor')
        print(ports['bad'].model)
        mock_client.return_value.get_devices.return_value = \
            [mock.MagicMock(ports=ports)]
        assert sensor.setup(self.hass, self.GOOD_CONFIG)
        for ident, port in ports.items():
            if ident != 'bad':
                mock_sensor.assert_any_call(port, self.hass)
        assert mock.call(ports['bad'], self.hass) not in mock_sensor.mock_calls


class TestMfiSensor(unittest.TestCase):
    """Test for mFi sensor platform."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.port = mock.MagicMock()
        self.sensor = mfi.MfiSensor(self.port, self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        self.assertEqual(self.port.label, self.sensor.name)

    def test_uom_temp(self):
        """Test the UOM temperature."""
        self.port.tag = 'temperature'
        self.assertEqual(TEMP_CELSIUS, self.sensor.unit_of_measurement)

    def test_uom_power(self):
        """Test the UOEM power."""
        self.port.tag = 'active_pwr'
        self.assertEqual('Watts', self.sensor.unit_of_measurement)

    def test_uom_digital(self):
        """Test the UOM digital input."""
        self.port.model = 'Input Digital'
        self.assertEqual('State', self.sensor.unit_of_measurement)

    def test_uom_unknown(self):
        """Test the UOM."""
        self.port.tag = 'balloons'
        self.assertEqual('balloons', self.sensor.unit_of_measurement)

    def test_uom_uninitialized(self):
        """Test that the UOM defaults if not initialized."""
        type(self.port).tag = mock.PropertyMock(side_effect=ValueError)
        self.assertEqual('State', self.sensor.unit_of_measurement)

    def test_state_digital(self):
        """Test the digital input."""
        self.port.model = 'Input Digital'
        self.port.value = 0
        self.assertEqual(mfi.STATE_OFF, self.sensor.state)
        self.port.value = 1
        self.assertEqual(mfi.STATE_ON, self.sensor.state)
        self.port.value = 2
        self.assertEqual(mfi.STATE_ON, self.sensor.state)

    def test_state_digits(self):
        """Test the state of digits."""
        self.port.tag = 'didyoucheckthedict?'
        self.port.value = 1.25
        with mock.patch.dict(mfi.DIGITS, {'didyoucheckthedict?': 1}):
            self.assertEqual(1.2, self.sensor.state)
        with mock.patch.dict(mfi.DIGITS, {}):
            self.assertEqual(1.0, self.sensor.state)

    def test_state_uninitialized(self):
        """Test the state of uninitialized sensors."""
        type(self.port).tag = mock.PropertyMock(side_effect=ValueError)
        self.assertEqual(mfi.STATE_OFF, self.sensor.state)

    def test_update(self):
        """Test the update."""
        self.sensor.update()
        self.port.refresh.assert_called_once_with()
