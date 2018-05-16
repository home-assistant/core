"""Test for Melissa climate component."""
import unittest
from unittest.mock import Mock, patch
import json

from asynctest import mock

from homeassistant.components.climate import (
    melissa, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    SUPPORT_ON_OFF, SUPPORT_FAN_MODE, STATE_HEAT, STATE_FAN_ONLY, STATE_DRY,
    STATE_COOL, STATE_AUTO
)
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.const import (
    TEMP_CELSIUS, STATE_ON, ATTR_TEMPERATURE, STATE_OFF, STATE_IDLE
)
from tests.common import get_test_home_assistant, load_fixture


class TestMelissa(unittest.TestCase):
    """Tests for Melissa climate."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up test variables."""
        self.hass = get_test_home_assistant()
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
        self.assertEqual("Melissa 12345678", self.thermostat.name)

    def test_is_on(self):
        """Test name property."""
        self.assertTrue(self.thermostat.is_on)
        self.thermostat._cur_settings = None
        self.assertFalse(self.thermostat.is_on)

    def test_current_fan_mode(self):
        """Test current_fan_mode property."""
        self.thermostat.update()
        self.assertEqual(SPEED_LOW, self.thermostat.current_fan_mode)
        self.thermostat._cur_settings = None
        self.assertEqual(None, self.thermostat.current_fan_mode)

    def test_current_temperature(self):
        """Test current temperature."""
        self.assertEqual(27.4, self.thermostat.current_temperature)

    def test_current_temperature_no_data(self):
        """Test current temperature without data."""
        self.thermostat._data = None
        self.assertIsNone(self.thermostat.current_temperature)

    def test_target_temperature_step(self):
        """Test current target_temperature_step."""
        self.assertEqual(1, self.thermostat.target_temperature_step)

    def test_current_operation(self):
        """Test current operation."""
        self.thermostat.update()
        self.assertEqual(self.thermostat.current_operation, STATE_HEAT)
        self.thermostat._cur_settings = None
        self.assertEqual(None, self.thermostat.current_operation)

    def test_operation_list(self):
        """Test the operation list."""
        self.assertEqual(
            [STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_HEAT],
            self.thermostat.operation_list
        )

    def test_fan_list(self):
        """Test the fan list."""
        self.assertEqual(
            [STATE_AUTO, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM],
            self.thermostat.fan_list
        )

    def test_target_temperature(self):
        """Test target temperature."""
        self.assertEqual(16, self.thermostat.target_temperature)
        self.thermostat._cur_settings = None
        self.assertEqual(None, self.thermostat.target_temperature)

    def test_state(self):
        """Test state."""
        self.assertEqual(STATE_ON, self.thermostat.state)
        self.thermostat._cur_settings = None
        self.assertEqual(None, self.thermostat.state)

    def test_temperature_unit(self):
        """Test temperature unit."""
        self.assertEqual(TEMP_CELSIUS, self.thermostat.temperature_unit)

    def test_min_temp(self):
        """Test min temp."""
        self.assertEqual(16, self.thermostat.min_temp)

    def test_max_temp(self):
        """Test max temp."""
        self.assertEqual(30, self.thermostat.max_temp)

    def test_supported_features(self):
        """Test supported_features property."""
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                    SUPPORT_ON_OFF | SUPPORT_FAN_MODE)
        self.assertEqual(features, self.thermostat.supported_features)

    def test_set_temperature(self):
        """Test set_temperature."""
        self.api.send.return_value = True
        self.thermostat.update()
        self.thermostat.set_temperature(**{ATTR_TEMPERATURE: 25})
        self.assertEqual(25, self.thermostat.target_temperature)

    def test_fan_mode(self):
        """Test set_fan_mode."""
        self.api.send.return_value = True
        self.thermostat.set_fan_mode(SPEED_HIGH)
        self.assertEqual(SPEED_HIGH, self.thermostat.current_fan_mode)

    def test_set_operation_mode(self):
        """Test set_operation_mode."""
        self.api.send.return_value = True
        self.thermostat.set_operation_mode(STATE_COOL)
        self.assertEqual(STATE_COOL, self.thermostat.current_operation)

    def test_turn_on(self):
        """Test turn_on."""
        self.thermostat.turn_on()
        self.assertTrue(self.thermostat.state)

    def test_turn_off(self):
        """Test turn_off."""
        self.thermostat.turn_off()
        self.assertEqual(STATE_OFF, self.thermostat.state)

    def test_send(self):
        """Test send."""
        self.thermostat.update()
        self.assertTrue(self.thermostat.send(
            {'fan': self.api.FAN_MEDIUM}))
        self.assertEqual(SPEED_MEDIUM, self.thermostat.current_fan_mode)
        self.api.send.return_value = False
        self.thermostat._cur_settings = None
        self.assertFalse(self.thermostat.send({
            'fan': self.api.FAN_LOW}))
        self.assertNotEqual(SPEED_LOW, self.thermostat.current_fan_mode)
        self.assertIsNone(self.thermostat._cur_settings)

    @mock.patch('homeassistant.components.climate.melissa._LOGGER.warning')
    def test_update(self, mocked_warning):
        """Test update."""
        self.thermostat.update()
        self.assertEqual(SPEED_LOW, self.thermostat.current_fan_mode)
        self.assertEqual(STATE_HEAT, self.thermostat.current_operation)
        self.thermostat._api.status.side_effect = KeyError('boom')
        self.thermostat.update()
        mocked_warning.assert_called_once_with(
            'Unable to update entity %s', self.thermostat.entity_id)

    def test_melissa_state_to_hass(self):
        """Test for translate melissa states to hass."""
        self.assertEqual(STATE_OFF, self.thermostat.melissa_state_to_hass(0))
        self.assertEqual(STATE_ON, self.thermostat.melissa_state_to_hass(1))
        self.assertEqual(STATE_IDLE, self.thermostat.melissa_state_to_hass(2))
        self.assertEqual(None,
                         self.thermostat.melissa_state_to_hass(3))

    def test_melissa_op_to_hass(self):
        """Test for translate melissa operations to hass."""
        self.assertEqual(STATE_FAN_ONLY, self.thermostat.melissa_op_to_hass(1))
        self.assertEqual(STATE_HEAT, self.thermostat.melissa_op_to_hass(2))
        self.assertEqual(STATE_COOL, self.thermostat.melissa_op_to_hass(3))
        self.assertEqual(STATE_DRY, self.thermostat.melissa_op_to_hass(4))
        self.assertEqual(
            None, self.thermostat.melissa_op_to_hass(5))

    def test_melissa_fan_to_hass(self):
        """Test for translate melissa fan state to hass."""
        self.assertEqual(STATE_AUTO, self.thermostat.melissa_fan_to_hass(0))
        self.assertEqual(SPEED_LOW, self.thermostat.melissa_fan_to_hass(1))
        self.assertEqual(SPEED_MEDIUM, self.thermostat.melissa_fan_to_hass(2))
        self.assertEqual(SPEED_HIGH, self.thermostat.melissa_fan_to_hass(3))
        self.assertEqual(None, self.thermostat.melissa_fan_to_hass(4))

    @mock.patch('homeassistant.components.climate.melissa._LOGGER.warning')
    def test_hass_mode_to_melissa(self, mocked_warning):
        """Test for hass operations to melssa."""
        self.assertEqual(
            1, self.thermostat.hass_mode_to_melissa(STATE_FAN_ONLY))
        self.assertEqual(2, self.thermostat.hass_mode_to_melissa(STATE_HEAT))
        self.assertEqual(3, self.thermostat.hass_mode_to_melissa(STATE_COOL))
        self.assertEqual(4, self.thermostat.hass_mode_to_melissa(STATE_DRY))
        self.thermostat.hass_mode_to_melissa("test")
        mocked_warning.assert_called_once_with(
            "Melissa have no setting for %s mode", "test")

    @mock.patch('homeassistant.components.climate.melissa._LOGGER.warning')
    def test_hass_fan_to_melissa(self, mocked_warning):
        """Test for translate melissa states to hass."""
        self.assertEqual(0, self.thermostat.hass_fan_to_melissa(STATE_AUTO))
        self.assertEqual(1, self.thermostat.hass_fan_to_melissa(SPEED_LOW))
        self.assertEqual(2, self.thermostat.hass_fan_to_melissa(SPEED_MEDIUM))
        self.assertEqual(3, self.thermostat.hass_fan_to_melissa(SPEED_HIGH))
        self.thermostat.hass_fan_to_melissa("test")
        mocked_warning.assert_called_once_with(
            "Melissa have no setting for %s fan mode", "test")
