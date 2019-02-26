"""Test the Dyson air quality component."""
import unittest
from unittest import mock

from libpurecool.dyson import DysonAccount
from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_state_v2 import DysonPureCoolV2State

from homeassistant.components import dyson as dyson_parent
from tests.common import get_test_home_assistant


class MockDysonV2State(DysonPureCoolV2State):
    """Mock Dyson purecool v2 state."""

    def __init__(self):
        """Create new Mock Dyson purecool v2 state."""
        pass


def _get_dyson_purecool_device():
    """Return a valid device provide by Dyson web services."""
    device = mock.Mock(spec=DysonPureCool)
    device.serial = "XX-XXXXX-XX"
    device.name = "Device_name"
    device.connect = mock.Mock(return_value=True)
    device.auto_connect = mock.Mock(return_value=True)
    device.environment_state = mock.Mock()
    device.environmental_state.particulate_matter_25 = 15
    device.environmental_state.particulate_matter_10 = 12
    device.environmental_state.nitrogen_dioxide = 20
    device.environmental_state.volatile_organic_compounds = 35
    return device


def _get_config():
    """Return a config dictionary."""
    return {dyson_parent.DOMAIN: {
        dyson_parent.CONF_USERNAME: "email",
        dyson_parent.CONF_PASSWORD: "password",
        dyson_parent.CONF_LANGUAGE: "GB",
        dyson_parent.CONF_DEVICES: [
            {
                "device_id": "XX-XXXXX-XX",
                "device_ip": "192.168.0.1"
            }
        ]
    }}


class DysonPurecoolTest(unittest.TestCase):
    """Dyson purecool fan component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_async_purecool_added_to_hass(self, mocked_login, mocked_devices):
        """Test async added to hass."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        assert mocked_devices.return_value[0].add_message_listener.called

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_on_message(self, mocked_login, mocked_devices):
        """Test on message for purecool air quality sensor."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        air_sensor = self.hass.data['air_quality']\
            .get_entity('air_quality.device_name')
        air_sensor.schedule_update_ha_state = mock.Mock()
        air_sensor.on_message(MockDysonV2State())
        air_sensor.schedule_update_ha_state.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_empty_state(self, mocked_login):
        """Test purecool air quality sensor with no status."""
        test_device = _get_dyson_purecool_device()
        test_device.environmental_state = None
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            air_sensor = self.hass.data['air_quality']\
                .get_entity('air_quality.device_name')
            assert air_sensor.particulate_matter_2_5 is None

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_values(self, mocked_login, mocked_devices):
        """Test purecool air quality sensor values."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        air_sensor = self.hass.data['air_quality']\
            .get_entity('air_quality.device_name')
        assert air_sensor.should_poll is False
        assert air_sensor.name == 'Device_name'
        assert air_sensor.attribution == 'Dyson purifier air quality sensor'
        assert air_sensor.particulate_matter_2_5 == 15
        assert air_sensor.particulate_matter_10 == 12
        assert air_sensor.nitrogen_dioxide == 20
        assert air_sensor.volatile_organic_compounds == 35
        assert air_sensor.volatile_organic_compounds == 35

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_state_attributes(self, mocked_login, mocked_devices):
        """Test purecool air quality state attributes."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        air_sensor = self.hass.data['air_quality']\
            .get_entity('air_quality.device_name')
        state_attributes = air_sensor.state_attributes
        assert 'test' not in state_attributes
        assert 'attribution' in state_attributes
        assert 'nitrogen_dioxide' in state_attributes
        assert 'particulate_matter_10' in state_attributes
        assert 'particulate_matter_2_5' in state_attributes
        assert 'volatile_organic_compounds' in state_attributes
