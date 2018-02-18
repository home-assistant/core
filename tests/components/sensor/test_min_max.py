"""The test for the min/max sensor platform."""
import unittest

from homeassistant import setup
from homeassistant.const import (
    STATE_UNKNOWN, ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from tests.common import assert_setup_component, get_test_home_assistant


CONFIG = {
    'sensor': [
        {'platform': 'min_max',
         'sensors': {
             'test_min_max': {
                 'entity_ids': [
                     'sensor.test_1',
                     'sensor.test_2',
                     'sensor.test_3'
                 ]}
         }}
    ]
}

MIN_MAX_SENSOR = 'sensor.test_min_max'
CONFIG_MIN_MAX = CONFIG['sensor'][0]['sensors']['test_min_max']


VALUES = [17, 20, 15.3]
COUNT = len(VALUES)
MIN = min(VALUES)
MAX = max(VALUES)
MEAN = round(sum(VALUES) / COUNT, 2)
MEAN_1_DIGIT = round(sum(VALUES) / COUNT, 1)
MEAN_4_DIGITS = round(sum(VALUES) / COUNT, 4)


class TestMinMaxSensor(unittest.TestCase):
    """Test the min/max sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_min_sensor(self):
        """Test the min sensor."""
        CONFIG_MIN_MAX['type'] = 'min'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(MIN)), state.state)
        self.assertEqual(MAX, state.attributes.get('max_value'))
        self.assertEqual(MEAN, state.attributes.get('mean'))

    def test_max_sensor(self):
        """Test the max sensor."""
        CONFIG_MIN_MAX['type'] = 'max'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(MAX)), state.state)
        self.assertEqual(MIN, state.attributes.get('min_value'))
        self.assertEqual(MEAN, state.attributes.get('mean'))

    def test_mean_sensor(self):
        """Test the mean sensor."""
        CONFIG_MIN_MAX['type'] = 'mean'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(MEAN)), state.state)
        self.assertEqual(MIN, state.attributes.get('min_value'))
        self.assertEqual(MAX, state.attributes.get('max_value'))

    def test_mean_1_digit_sensor(self):
        """Test the mean with 1-digit precision sensor."""
        CONFIG_MIN_MAX['type'] = 'mean'
        CONFIG_MIN_MAX['round_digits'] = 1
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(MEAN_1_DIGIT)), state.state)
        self.assertEqual(MIN, state.attributes.get('min_value'))
        self.assertEqual(MAX, state.attributes.get('max_value'))

    def test_mean_4_digit_sensor(self):
        """Test the mean with 4-digit precision sensor."""
        CONFIG_MIN_MAX['type'] = 'mean'
        CONFIG_MIN_MAX['round_digits'] = 4
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(MEAN_4_DIGITS)), state.state)
        self.assertEqual(MIN, state.attributes.get('min_value'))
        self.assertEqual(MAX, state.attributes.get('max_value'))

    def test_not_enough_sensor_value(self):
        """Test that there is nothing done if not enough values available."""
        CONFIG_MIN_MAX['type'] = 'max'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        self.hass.states.set(entity_ids[0], STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)
        self.assertEqual(STATE_UNKNOWN, state.state)

        self.hass.states.set(entity_ids[1], VALUES[1])
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)
        self.assertNotEqual(STATE_UNKNOWN, state.state)

        self.hass.states.set(entity_ids[2], STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)
        self.assertNotEqual(STATE_UNKNOWN, state.state)

        self.hass.states.set(entity_ids[1], STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)
        self.assertEqual(STATE_UNKNOWN, state.state)

    # pylint: disable=invalid-name
    def test_different_unit_of_measurement(self):
        """Test for different unit of measurement."""
        CONFIG_MIN_MAX['type'] = 'mean'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']

        self.hass.states.set(entity_ids[0], VALUES[0],
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(str(float(VALUES[0])), state.state)
        self.assertEqual('°C', state.attributes.get('unit_of_measurement'))

        self.hass.states.set(entity_ids[1], VALUES[1],
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(STATE_UNKNOWN, state.state)
        self.assertEqual('ERR', state.attributes.get('unit_of_measurement'))

        self.hass.states.set(entity_ids[2], VALUES[2],
                             {ATTR_UNIT_OF_MEASUREMENT: '%'})
        self.hass.block_till_done()

        state = self.hass.states.get(MIN_MAX_SENSOR)

        self.assertEqual(STATE_UNKNOWN, state.state)
        self.assertEqual('ERR', state.attributes.get('unit_of_measurement'))

    def test_last_sensor(self):
        """Test the last sensor."""
        CONFIG_MIN_MAX['type'] = 'last'
        CONFIG_MIN_MAX.pop('round_digits', '')
        with assert_setup_component(1, 'sensor'):
            setup.setup_component(self.hass, 'sensor', CONFIG)

        entity_ids = CONFIG_MIN_MAX['entity_ids']
        state = self.hass.states.get(MIN_MAX_SENSOR)

        for entity_id, value in dict(zip(entity_ids, VALUES)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()
            state = self.hass.states.get(MIN_MAX_SENSOR)
            self.assertEqual(str(float(value)), state.state)

        self.assertEqual(MIN, state.attributes.get('min_value'))
        self.assertEqual(MAX, state.attributes.get('max_value'))
        self.assertEqual(MEAN, state.attributes.get('mean'))
