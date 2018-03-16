"""Test different accessory types: Sensors."""
import unittest

from homeassistant.components.homekit.const import PROP_CELSIUS
from homeassistant.components.homekit.type_sensors import (
    TemperatureSensor, HumiditySensor, calc_temperature, calc_humidity)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from tests.common import get_test_home_assistant


def test_calc_temperature():
    """Test if temperature in Celsius is calculated correctly."""
    assert calc_temperature(STATE_UNKNOWN) is None
    assert calc_temperature('test') is None

    assert calc_temperature('20') == 20
    assert calc_temperature('20.12', TEMP_CELSIUS) == 20.12
    assert calc_temperature('75.2', TEMP_FAHRENHEIT) == 24


def test_calc_humidity():
    """Test if humidity is a integer."""
    assert calc_humidity(STATE_UNKNOWN) is None
    assert calc_humidity('test') is None

    assert calc_humidity('20') == 20
    assert calc_humidity('75.2') == 75.2


class TestHomekitSensors(unittest.TestCase):
    """Test class for all accessory types regarding sensors."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temperature(self):
        """Test if accessory is updated after state change."""
        entity_id = 'sensor.temperature'

        acc = TemperatureSensor(self.hass, entity_id, 'Temperature', aid=2)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 10)  # Sensor

        self.assertEqual(acc.char_temp.value, 0.0)
        for key, value in PROP_CELSIUS.items():
            self.assertEqual(acc.char_temp.properties[key], value)

        self.hass.states.set(entity_id, STATE_UNKNOWN,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        self.hass.states.set(entity_id, '20',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_temp.value, 20)

        self.hass.states.set(entity_id, '75.2',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
        self.hass.block_till_done()
        self.assertEqual(acc.char_temp.value, 24)

    def test_humidity(self):
        """Test if accessory is updated after state change."""
        entity_id = 'sensor.humidity'

        acc = HumiditySensor(self.hass, entity_id, 'Humidity', aid=2)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 10)  # Sensor

        self.assertEqual(acc.char_humidity.value, 0)

        self.hass.states.set(entity_id, STATE_UNKNOWN,
                             {ATTR_UNIT_OF_MEASUREMENT: "%"})
        self.hass.block_till_done()

        self.hass.states.set(entity_id, '20', {ATTR_UNIT_OF_MEASUREMENT: "%"})
        self.hass.block_till_done()
        self.assertEqual(acc.char_humidity.value, 20)
