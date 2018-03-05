"""Test different accessory types: Thermostats."""
import unittest
from unittest.mock import patch
import time

from homeassistant.core import callback
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_TEMPERATURE,
    ATTR_OPERATION_MODE, STATE_HEAT)
from homeassistant.components.homekit.thermostats import Thermostat
from homeassistant.const import (
    ATTR_SERVICE, EVENT_CALL_SERVICE, ATTR_SERVICE_DATA)

from tests.common import get_test_home_assistant
from tests.mock.homekit import get_patch_paths, mock_preload_service

PATH_ACC, PATH_FILE = get_patch_paths('thermostats')


class TestHomekitThermostats(unittest.TestCase):
    """Test class for all accessory types regarding thermostats."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []

        @callback
        def record_event(event):
            """Track called event."""
            self.events.append(event)

        self.hass.bus.listen(EVENT_CALL_SERVICE, record_event)

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_switch_set_state(self):
        """Test if accessory and HA are updated accordingly."""
        climate = 'climate.testclimate'

        with patch(PATH_ACC, side_effect=mock_preload_service):
            with patch(PATH_FILE, side_effect=mock_preload_service):
                acc = Thermostat(self.hass, climate, 'Climate')
                acc.run()

        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 0)
        self.assertEqual(acc.char_current_temp.value, 0.0)
        self.assertEqual(acc.char_target_temp.value, 0.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, 'heat',
                             {ATTR_OPERATION_MODE: STATE_HEAT,
                              ATTR_TEMPERATURE: 21.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              'unit_of_measurement': '°C'})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 21.0)
        self.assertEqual(acc.char_current_heat_cool.value, 1)
        self.assertEqual(acc.char_target_heat_cool.value, 1)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, 'off',
                             {ATTR_OPERATION_MODE: 'off',
                              ATTR_TEMPERATURE: 21.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              'unit_of_measurement': '°C'})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 21.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 0)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        # Set from HomeKit
        acc.char_target_temp.set_value(19.0)
        self.hass.block_till_done()
        time.sleep(2)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'set_temperature')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_TEMPERATURE], 19.0)
        self.assertEqual(acc.char_target_temp.value, 19.0)

        acc.char_target_heat_cool.set_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'set_operation_mode')
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA][ATTR_OPERATION_MODE], STATE_HEAT)
        self.assertEqual(acc.char_target_heat_cool.value, 1)
