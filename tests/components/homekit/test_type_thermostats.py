"""Test different accessory types: Thermostats."""
import unittest

from homeassistant.core import callback
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH, ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST, STATE_COOL, STATE_HEAT, STATE_AUTO)
from homeassistant.const import (
    ATTR_SERVICE, ATTR_SERVICE_DATA, ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT, EVENT_CALL_SERVICE,
    STATE_OFF, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from tests.common import get_test_home_assistant
from tests.components.homekit.test_accessories import patch_debounce


class TestHomekitThermostats(unittest.TestCase):
    """Test class for all accessory types regarding thermostats."""

    @classmethod
    def setUpClass(cls):
        """Setup Thermostat class import and debounce patcher."""
        cls.patcher = patch_debounce()
        cls.patcher.start()
        _import = __import__(
            'homeassistant.components.homekit.type_thermostats',
            fromlist=['Thermostat'])
        cls.thermostat_cls = _import.Thermostat

    @classmethod
    def tearDownClass(cls):
        """Stop debounce patcher."""
        cls.patcher.stop()

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

    def test_default_thermostat(self):
        """Test if accessory and HA are updated accordingly."""
        climate = 'climate.test'

        self.hass.states.set(climate, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
        self.hass.block_till_done()
        acc = self.thermostat_cls(self.hass, 'Climate', climate,
                                  2, config=None)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 9)  # Thermostat

        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 0)
        self.assertEqual(acc.char_current_temp.value, 21.0)
        self.assertEqual(acc.char_target_temp.value, 21.0)
        self.assertEqual(acc.char_display_units.value, 0)
        self.assertEqual(acc.char_cooling_thresh_temp, None)
        self.assertEqual(acc.char_heating_thresh_temp, None)

        self.hass.states.set(climate, STATE_HEAT,
                             {ATTR_OPERATION_MODE: STATE_HEAT,
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 1)
        self.assertEqual(acc.char_target_heat_cool.value, 1)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_HEAT,
                             {ATTR_OPERATION_MODE: STATE_HEAT,
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 23.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 1)
        self.assertEqual(acc.char_current_temp.value, 23.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_COOL,
                             {ATTR_OPERATION_MODE: STATE_COOL,
                              ATTR_TEMPERATURE: 20.0,
                              ATTR_CURRENT_TEMPERATURE: 25.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 20.0)
        self.assertEqual(acc.char_current_heat_cool.value, 2)
        self.assertEqual(acc.char_target_heat_cool.value, 2)
        self.assertEqual(acc.char_current_temp.value, 25.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_COOL,
                             {ATTR_OPERATION_MODE: STATE_COOL,
                              ATTR_TEMPERATURE: 20.0,
                              ATTR_CURRENT_TEMPERATURE: 19.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 20.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 2)
        self.assertEqual(acc.char_current_temp.value, 19.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_OFF,
                             {ATTR_OPERATION_MODE: STATE_OFF,
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 0)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 1)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 25.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 2)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 25.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                              ATTR_TEMPERATURE: 22.0,
                              ATTR_CURRENT_TEMPERATURE: 22.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 22.0)
        self.assertEqual(acc.char_display_units.value, 0)

        # Set from HomeKit
        acc.char_target_temp.client_update_value(19.0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'set_temperature')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_TEMPERATURE], 19.0)
        self.assertEqual(acc.char_target_temp.value, 19.0)

        acc.char_target_heat_cool.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'set_operation_mode')
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA][ATTR_OPERATION_MODE],
            STATE_HEAT)
        self.assertEqual(acc.char_target_heat_cool.value, 1)

    def test_auto_thermostat(self):
        """Test if accessory and HA are updated accordingly."""
        climate = 'climate.test'

        # support_auto = True
        self.hass.states.set(climate, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 6})
        self.hass.block_till_done()
        acc = self.thermostat_cls(self.hass, 'Climate', climate,
                                  2, config=None)
        acc.run()

        self.assertEqual(acc.char_cooling_thresh_temp.value, 23.0)
        self.assertEqual(acc.char_heating_thresh_temp.value, 19.0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_TARGET_TEMP_HIGH: 22.0,
                              ATTR_TARGET_TEMP_LOW: 20.0,
                              ATTR_CURRENT_TEMPERATURE: 18.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_heating_thresh_temp.value, 20.0)
        self.assertEqual(acc.char_cooling_thresh_temp.value, 22.0)
        self.assertEqual(acc.char_current_heat_cool.value, 1)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 18.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_TARGET_TEMP_HIGH: 23.0,
                              ATTR_TARGET_TEMP_LOW: 19.0,
                              ATTR_CURRENT_TEMPERATURE: 24.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_heating_thresh_temp.value, 19.0)
        self.assertEqual(acc.char_cooling_thresh_temp.value, 23.0)
        self.assertEqual(acc.char_current_heat_cool.value, 2)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 24.0)
        self.assertEqual(acc.char_display_units.value, 0)

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_TARGET_TEMP_HIGH: 23.0,
                              ATTR_TARGET_TEMP_LOW: 19.0,
                              ATTR_CURRENT_TEMPERATURE: 21.0,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_heating_thresh_temp.value, 19.0)
        self.assertEqual(acc.char_cooling_thresh_temp.value, 23.0)
        self.assertEqual(acc.char_current_heat_cool.value, 0)
        self.assertEqual(acc.char_target_heat_cool.value, 3)
        self.assertEqual(acc.char_current_temp.value, 21.0)
        self.assertEqual(acc.char_display_units.value, 0)

        # Set from HomeKit
        acc.char_heating_thresh_temp.client_update_value(20.0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'set_temperature')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_TARGET_TEMP_LOW], 20.0)
        self.assertEqual(acc.char_heating_thresh_temp.value, 20.0)

        acc.char_cooling_thresh_temp.client_update_value(25.0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'set_temperature')
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA][ATTR_TARGET_TEMP_HIGH],
            25.0)
        self.assertEqual(acc.char_cooling_thresh_temp.value, 25.0)

    def test_thermostat_fahrenheit(self):
        """Test if accessory and HA are updated accordingly."""
        climate = 'climate.test'

        # support_auto = True
        self.hass.states.set(climate, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 6})
        self.hass.block_till_done()
        acc = self.thermostat_cls(self.hass, 'Climate', climate,
                                  2, config=None)
        acc.run()

        self.hass.states.set(climate, STATE_AUTO,
                             {ATTR_OPERATION_MODE: STATE_AUTO,
                              ATTR_TARGET_TEMP_HIGH: 75.2,
                              ATTR_TARGET_TEMP_LOW: 68,
                              ATTR_TEMPERATURE: 71.6,
                              ATTR_CURRENT_TEMPERATURE: 73.4,
                              ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
        self.hass.block_till_done()
        self.assertEqual(acc.char_heating_thresh_temp.value, 20.0)
        self.assertEqual(acc.char_cooling_thresh_temp.value, 24.0)
        self.assertEqual(acc.char_current_temp.value, 23.0)
        self.assertEqual(acc.char_target_temp.value, 22.0)
        self.assertEqual(acc.char_display_units.value, 1)

        # Set from HomeKit
        acc.char_cooling_thresh_temp.client_update_value(23)
        self.hass.block_till_done()
        service_data = self.events[-1].data[ATTR_SERVICE_DATA]
        self.assertEqual(service_data[ATTR_TARGET_TEMP_HIGH], 73.4)
        self.assertEqual(service_data[ATTR_TARGET_TEMP_LOW], 68)

        acc.char_heating_thresh_temp.client_update_value(22)
        self.hass.block_till_done()
        service_data = self.events[-1].data[ATTR_SERVICE_DATA]
        self.assertEqual(service_data[ATTR_TARGET_TEMP_HIGH], 73.4)
        self.assertEqual(service_data[ATTR_TARGET_TEMP_LOW], 71.6)

        acc.char_target_temp.client_update_value(24.0)
        self.hass.block_till_done()
        service_data = self.events[-1].data[ATTR_SERVICE_DATA]
        self.assertEqual(service_data[ATTR_TEMPERATURE], 75.2)
