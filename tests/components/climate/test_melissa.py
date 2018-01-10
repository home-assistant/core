"""Test for Melissa climate component."""
import unittest
from unittest.mock import Mock, patch
import json

from homeassistant.components.climate import melissa, \
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF, \
    SUPPORT_FAN_MODE, STATE_HEAT, STATE_FAN_ONLY, STATE_DRY, STATE_COOL, \
    STATE_AUTO
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.const import TEMP_CELSIUS, STATE_ON, ATTR_TEMPERATURE, \
    STATE_OFF, STATE_IDLE, STATE_UNKNOWN
from tests.common import get_test_home_assistant, load_fixture
from tests.components.test_melissa import VALID_CONFIG


class TestMelissa(unittest.TestCase):
    """Tests for Melissa climate."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up test variables."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG
        self._serial = '12345678'

        self.api = Mock()
        self.api.fetch_devices.return_value = json.loads(load_fixture(
            'melissa_fetch_devices.json'
        ))
        self.api.cur_settings.return_value = json.loads(load_fixture(
            'melissa_cur_settings.json'
        ))
        self.api.status.return_value = json.loads(load_fixture(
            'melissa_status.json'
        ))
        self.api.STATE_OFF = 0
        self.api.STATE_ON = 1
        self.api.STATE_IDLE = 2

        self.api.MODE_AUTO = 0
        self.api.MODE_FAN = 1
        self.api.MODE_HEAT = 2
        self.api.MODE_COOL = 3
        self.api.MODE_DRY = 4

        self.api.FAN_AUTO = 0
        self.api.FAN_LOW = 1
        self.api.FAN_MEDIUM = 2
        self.api.FAN_HIGH = 3

        self.api.STATE = 'state'
        self.api.MODE = 'mode'
        self.api.FAN = 'fan'
        self.api.TEMP = 'temp'

        device = self.api.fetch_devices()[self._serial]
        self.thermostat = melissa.MelissaClimate(
            self.api, device['serial_number'], device)
        self.thermostat.update()

    def tearDown(self):  # pylint: disable=invalid-name
        """Teardown this test class. Stop hass."""
        self.hass.stop()

    @patch("homeassistant.components.climate.melissa.MelissaClimate")
    def test_setup_platform(self, mocked_thermostat):
        """Test setup_platform."""
        device = self.api.fetch_devices()[self._serial]
        thermostat = mocked_thermostat(self.api, device['serial_number'],
                                       device)
        thermostats = [thermostat]

        self.hass.data[DATA_MELISSA] = self.api

        config = {}
        add_devices = Mock()
        discovery_info = {}

        melissa.setup_platform(self.hass, config, add_devices, discovery_info)
        add_devices.assert_called_once_with(thermostats)

    def test_get_name(self):
        """Test name property."""
        self.assertEqual(self.thermostat.name, "Melissa 12345678")

    def test_is_on(self):
        """Test name property."""
        self.assertEqual(self.thermostat.is_on, True)

    def test_icon(self):
        """Test icon property."""
        self.assertEqual(self.thermostat.icon, "mdi:thermometer")

    def test_current_fan_mode(self):
        """Test current_fan_mode property."""
        self.thermostat.update()
        self.assertEqual(self.thermostat.current_fan_mode, SPEED_LOW)

    def test_current_temperature(self):
        """Test current temperature."""
        self.assertEqual(self.thermostat.current_temperature, 27.4)

    def test_target_temperature_step(self):
        """Test current target_temperature_step."""
        self.assertEqual(self.thermostat.target_temperature_step, 1)

    def test_current_operation(self):
        """Test current operation."""
        self.thermostat.update()
        self.assertEqual(self.thermostat.current_operation, STATE_HEAT)

    def test_operation_list(self):
        """Test the operation list."""
        self.assertEqual(
            self.thermostat.operation_list,
            [STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY]
        )

    def test_fan_list(self):
        """Test the fan list."""
        self.assertEqual(
            self.thermostat.fan_list,
            [STATE_AUTO, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
        )

    def test_target_temperature(self):
        """Test target temperature."""
        self.assertEqual(self.thermostat.target_temperature, 16)

    def test_state(self):
        """Test state."""
        self.assertEqual(self.thermostat.state, STATE_ON)

    def test_temperature_unit(self):
        """Test temperature unit."""
        self.assertEqual(self.thermostat.temperature_unit, TEMP_CELSIUS)

    def test_min_temp(self):
        """Test min temp."""
        self.assertEqual(self.thermostat.min_temp, 16)

    def test_max_temp(self):
        """Test max temp."""
        self.assertEqual(self.thermostat.max_temp, 30)

    def test_supported_features(self):
        """Test supported_features property."""
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                    SUPPORT_ON_OFF | SUPPORT_FAN_MODE)
        self.assertEqual(self.thermostat.supported_features, features)

    def test_set_temperature(self):
        """Test set_temperature."""
        self.api.send.return_value = True
        self.thermostat.update()
        self.assertEqual(self.thermostat.set_temperature(
            **{ATTR_TEMPERATURE: 25}), True)
        self.assertEqual(self.thermostat.target_temperature, 25)

    def test_fan_mode(self):
        """Test set_fan_mode."""
        self.api.send.return_value = True
        self.assertEqual(self.thermostat.set_fan_mode(SPEED_LOW), True)
        self.assertEqual(self.thermostat.current_fan_mode, SPEED_LOW)

    def test_set_operation_mode(self):
        """Test set_operation_mode."""
        self.api.send.return_value = True
        self.assertEqual(self.thermostat.set_operation_mode(STATE_COOL), True)
        self.assertEqual(self.thermostat.current_operation, STATE_COOL)

    def test_turn_on(self):
        """Test turn_on."""
        self.assertEqual(self.thermostat.turn_on(), True)

    def test_turn_off(self):
        """Test turn_off."""
        self.assertEqual(self.thermostat.turn_off(), True)

    def test_send(self):
        """Test send."""
        self.thermostat.update()
        self.assertEqual(self.thermostat.send(
            {'fan': self.api.FAN_MEDIUM}), True)
        self.assertEqual(self.thermostat.current_fan_mode, SPEED_MEDIUM)
        self.api.send.return_value = False
        self.assertEqual(self.thermostat.send({
            'fan': self.api.FAN_LOW}), False)
        self.assertNotEquals(self.thermostat.current_fan_mode, SPEED_LOW)

    def test_update(self):
        """Test update."""
        self.thermostat.update()
        self.assertEqual(self.thermostat.current_fan_mode, SPEED_LOW)
        self.assertEqual(self.thermostat.current_operation, STATE_HEAT)

    def test_melissa_state_to_hass(self):
        """Test for translate melissa states to hass."""
        self.assertEqual(self.thermostat.melissa_state_to_hass(0), STATE_OFF)
        self.assertEqual(self.thermostat.melissa_state_to_hass(1), STATE_ON)
        self.assertEqual(self.thermostat.melissa_state_to_hass(2), STATE_IDLE)
        self.assertEqual(
            self.thermostat.melissa_state_to_hass(3), STATE_UNKNOWN)

    def test_melissa_op_to_hass(self):
        """Test for translate melissa operations to hass."""
        self.assertEqual(self.thermostat.melissa_op_to_hass(0), STATE_AUTO)
        self.assertEqual(self.thermostat.melissa_op_to_hass(1), STATE_FAN_ONLY)
        self.assertEqual(self.thermostat.melissa_op_to_hass(2), STATE_HEAT)
        self.assertEqual(self.thermostat.melissa_op_to_hass(3), STATE_COOL)
        self.assertEqual(self.thermostat.melissa_op_to_hass(4), STATE_DRY)
        self.assertEqual(
            self.thermostat.melissa_op_to_hass(5), STATE_UNKNOWN)

    def test_melissa_fan_to_hass(self):
        """Test for translate melissa fan state to hass."""
        self.assertEqual(self.thermostat.melissa_fan_to_hass(0), STATE_AUTO)
        self.assertEqual(self.thermostat.melissa_fan_to_hass(1), SPEED_LOW)
        self.assertEqual(self.thermostat.melissa_fan_to_hass(2), SPEED_MEDIUM)
        self.assertEqual(self.thermostat.melissa_fan_to_hass(3), SPEED_HIGH)

    def test_hass_mode_to_melissa(self):
        """Test for hass operations to melssa."""
        self.assertEqual(self.thermostat.hass_mode_to_melissa(STATE_AUTO), 0)
        self.assertEqual(
            self.thermostat.hass_mode_to_melissa(STATE_FAN_ONLY), 1)
        self.assertEqual(self.thermostat.hass_mode_to_melissa(STATE_HEAT), 2)
        self.assertEqual(self.thermostat.hass_mode_to_melissa(STATE_COOL), 3)
        self.assertEqual(self.thermostat.hass_mode_to_melissa(STATE_DRY), 4)

    def test_hass_fan_to_melissa(self):
        """Test for translate melissa states to hass."""
        self.assertEqual(self.thermostat.hass_fan_to_melissa(STATE_AUTO), 0)
        self.assertEqual(self.thermostat.hass_fan_to_melissa(SPEED_LOW), 1)
        self.assertEqual(self.thermostat.hass_fan_to_melissa(SPEED_MEDIUM), 2)
        self.assertEqual(self.thermostat.hass_fan_to_melissa(SPEED_HIGH), 3)
