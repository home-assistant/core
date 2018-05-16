"""The test for the NuHeat thermostat module."""
import unittest
from unittest.mock import Mock, patch
from tests.common import get_test_home_assistant

from homeassistant.components.climate import (
    SUPPORT_HOLD_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    STATE_HEAT,
    STATE_IDLE)
import homeassistant.components.climate.nuheat as nuheat
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

SCHEDULE_HOLD = 3
SCHEDULE_RUN = 1
SCHEDULE_TEMPORARY_HOLD = 2


class TestNuHeat(unittest.TestCase):
    """Tests for NuHeat climate."""

    # pylint: disable=protected-access, no-self-use

    def setUp(self):  # pylint: disable=invalid-name
        """Set up test variables."""
        serial_number = "12345"
        temperature_unit = "F"

        thermostat = Mock(
            serial_number=serial_number,
            room="Master bathroom",
            online=True,
            heating=True,
            temperature=2222,
            celsius=22,
            fahrenheit=72,
            max_celsius=69,
            max_fahrenheit=157,
            min_celsius=5,
            min_fahrenheit=41,
            schedule_mode=SCHEDULE_RUN,
            target_celsius=22,
            target_fahrenheit=72)

        thermostat.get_data = Mock()
        thermostat.resume_schedule = Mock()

        self.api = Mock()
        self.api.get_thermostat.return_value = thermostat

        self.hass = get_test_home_assistant()
        self.thermostat = nuheat.NuHeatThermostat(
            self.api, serial_number, temperature_unit)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop hass."""
        self.hass.stop()

    @patch("homeassistant.components.climate.nuheat.NuHeatThermostat")
    def test_setup_platform(self, mocked_thermostat):
        """Test setup_platform."""
        mocked_thermostat.return_value = self.thermostat
        thermostat = mocked_thermostat(self.api, "12345", "F")
        thermostats = [thermostat]

        self.hass.data[nuheat.NUHEAT_DOMAIN] = (self.api, ["12345"])

        config = {}
        add_devices = Mock()
        discovery_info = {}

        nuheat.setup_platform(self.hass, config, add_devices, discovery_info)
        add_devices.assert_called_once_with(thermostats, True)

    @patch("homeassistant.components.climate.nuheat.NuHeatThermostat")
    def test_resume_program_service(self, mocked_thermostat):
        """Test resume program service."""
        mocked_thermostat.return_value = self.thermostat
        thermostat = mocked_thermostat(self.api, "12345", "F")
        thermostat.resume_program = Mock()
        thermostat.schedule_update_ha_state = Mock()
        thermostat.entity_id = "climate.master_bathroom"

        self.hass.data[nuheat.NUHEAT_DOMAIN] = (self.api, ["12345"])
        nuheat.setup_platform(self.hass, {}, Mock(), {})

        # Explicit entity
        self.hass.services.call(nuheat.DOMAIN, nuheat.SERVICE_RESUME_PROGRAM,
                                {"entity_id": "climate.master_bathroom"}, True)

        thermostat.resume_program.assert_called_with()
        thermostat.schedule_update_ha_state.assert_called_with(True)

        thermostat.resume_program.reset_mock()
        thermostat.schedule_update_ha_state.reset_mock()

        # All entities
        self.hass.services.call(
            nuheat.DOMAIN, nuheat.SERVICE_RESUME_PROGRAM, {}, True)

        thermostat.resume_program.assert_called_with()
        thermostat.schedule_update_ha_state.assert_called_with(True)

    def test_name(self):
        """Test name property."""
        self.assertEqual(self.thermostat.name, "Master bathroom")

    def test_icon(self):
        """Test name property."""
        self.assertEqual(self.thermostat.icon, "mdi:thermometer")

    def test_supported_features(self):
        """Test name property."""
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_HOLD_MODE |
                    SUPPORT_OPERATION_MODE)
        self.assertEqual(self.thermostat.supported_features, features)

    def test_temperature_unit(self):
        """Test temperature unit."""
        self.assertEqual(self.thermostat.temperature_unit, TEMP_FAHRENHEIT)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.temperature_unit, TEMP_CELSIUS)

    def test_current_temperature(self):
        """Test current temperature."""
        self.assertEqual(self.thermostat.current_temperature, 72)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.current_temperature, 22)

    def test_current_operation(self):
        """Test current operation."""
        self.assertEqual(self.thermostat.current_operation, STATE_HEAT)
        self.thermostat._thermostat.heating = False
        self.assertEqual(self.thermostat.current_operation, STATE_IDLE)

    def test_min_temp(self):
        """Test min temp."""
        self.assertEqual(self.thermostat.min_temp, 41)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.min_temp, 5)

    def test_max_temp(self):
        """Test max temp."""
        self.assertEqual(self.thermostat.max_temp, 157)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.max_temp, 69)

    def test_target_temperature(self):
        """Test target temperature."""
        self.assertEqual(self.thermostat.target_temperature, 72)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.target_temperature, 22)

    def test_current_hold_mode(self):
        """Test current hold mode."""
        self.thermostat._thermostat.schedule_mode = SCHEDULE_RUN
        self.assertEqual(self.thermostat.current_hold_mode, nuheat.MODE_AUTO)

        self.thermostat._thermostat.schedule_mode = SCHEDULE_HOLD
        self.assertEqual(
            self.thermostat.current_hold_mode, nuheat.MODE_HOLD_TEMPERATURE)

        self.thermostat._thermostat.schedule_mode = SCHEDULE_TEMPORARY_HOLD
        self.assertEqual(
            self.thermostat.current_hold_mode, nuheat.MODE_TEMPORARY_HOLD)

        self.thermostat._thermostat.schedule_mode = None
        self.assertEqual(
            self.thermostat.current_hold_mode, nuheat.MODE_AUTO)

    def test_operation_list(self):
        """Test the operation list."""
        self.assertEqual(
            self.thermostat.operation_list,
            [STATE_HEAT, STATE_IDLE]
        )

    def test_resume_program(self):
        """Test resume schedule."""
        self.thermostat.resume_program()
        self.thermostat._thermostat.resume_schedule.assert_called_once_with()
        self.assertTrue(self.thermostat._force_update)

    def test_set_hold_mode(self):
        """Test set hold mode."""
        self.thermostat.set_hold_mode("temperature")
        self.assertEqual(
            self.thermostat._thermostat.schedule_mode, SCHEDULE_HOLD)
        self.assertTrue(self.thermostat._force_update)

        self.thermostat.set_hold_mode("temporary_temperature")
        self.assertEqual(
            self.thermostat._thermostat.schedule_mode, SCHEDULE_TEMPORARY_HOLD)
        self.assertTrue(self.thermostat._force_update)

        self.thermostat.set_hold_mode("auto")
        self.assertEqual(
            self.thermostat._thermostat.schedule_mode, SCHEDULE_RUN)
        self.assertTrue(self.thermostat._force_update)

    def test_set_temperature(self):
        """Test set temperature."""
        self.thermostat.set_temperature(temperature=85)
        self.assertEqual(self.thermostat._thermostat.target_fahrenheit, 85)
        self.assertTrue(self.thermostat._force_update)

        self.thermostat._temperature_unit = "C"
        self.thermostat.set_temperature(temperature=23)
        self.assertEqual(self.thermostat._thermostat.target_celsius, 23)
        self.assertTrue(self.thermostat._force_update)

    @patch.object(nuheat.NuHeatThermostat, "_throttled_update")
    def test_update_without_throttle(self, throttled_update):
        """Test update without throttle."""
        self.thermostat._force_update = True
        self.thermostat.update()
        throttled_update.assert_called_once_with(no_throttle=True)
        self.assertFalse(self.thermostat._force_update)

    @patch.object(nuheat.NuHeatThermostat, "_throttled_update")
    def test_update_with_throttle(self, throttled_update):
        """Test update with throttle."""
        self.thermostat._force_update = False
        self.thermostat.update()
        throttled_update.assert_called_once_with()
        self.assertFalse(self.thermostat._force_update)

    def test_throttled_update(self):
        """Test update with throttle."""
        self.thermostat._throttled_update()
        self.thermostat._thermostat.get_data.assert_called_once_with()
