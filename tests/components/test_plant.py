"""Unit tests for platform/plant.py."""
import asyncio
import unittest
from datetime import datetime, timedelta

from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN,
                                 STATE_PROBLEM)
from homeassistant.components import recorder
import homeassistant.components.plant as plant
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, init_recorder_component


GOOD_DATA = {
    'moisture': 50,
    'battery': 90,
    'temperature': 23.4,
    'conductivity': 777,
    'brightness': 987,
}

BRIGHTNESS_ENTITIY = 'sensor.mqtt_plant_brightness'

GOOD_CONFIG = {
    'sensors': {
        'moisture': 'sensor.mqtt_plant_moisture',
        'battery': 'sensor.mqtt_plant_battery',
        'temperature': 'sensor.mqtt_plant_temperature',
        'conductivity': 'sensor.mqtt_plant_conductivity',
        'brightness': BRIGHTNESS_ENTITIY,
    },
    'min_moisture': 20,
    'max_moisture': 60,
    'min_battery': 17,
    'min_conductivity': 500,
    'min_temperature': 15,
    'min_brightness': 500,
}


class _MockState(object):

    def __init__(self, state=None):
        self.state = state


class TestPlant(unittest.TestCase):

    def setUp(self):
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @asyncio.coroutine
    def test_valid_data(self):
        """Test processing valid data."""
        sensor = plant.Plant(self.hass, 'my plant', GOOD_CONFIG)
        sensor.hass = self.hass
        for reading, value in GOOD_DATA.items():
            sensor.state_changed(
                GOOD_CONFIG['sensors'][reading], None,
                _MockState(value))
        assert sensor.state == 'ok'
        attrib = sensor.state_attributes
        for reading, value in GOOD_DATA.items():
            # battery level has a different name in
            # the JSON format than in hass
            assert attrib[reading] == value

    @asyncio.coroutine
    def test_low_battery(self):
        """Test processing with low battery data and limit set."""
        sensor = plant.Plant(self.hass, 'other plant', GOOD_CONFIG)
        sensor.hass = self.hass
        assert sensor.state_attributes['problem'] == 'none'
        sensor.state_changed('sensor.mqtt_plant_battery',
                             _MockState(45), _MockState(10))
        assert sensor.state == 'problem'
        assert sensor.state_attributes['problem'] == 'battery low'

    def test_update_states(self):
        plant_name = 'some_plant'
        assert setup_component(self.hass, plant.DOMAIN, {
            plant.DOMAIN: {
                plant_name: GOOD_CONFIG
            }
        })
        self.hass.states.set(BRIGHTNESS_ENTITIY, 1000,
                             {ATTR_UNIT_OF_MEASUREMENT: 'Lux'})
        self.hass.block_till_done()
        state = self.hass.states.get('plant.'+plant_name)
        self.assertEquals(STATE_PROBLEM, state.state)
        self.assertEquals(1000, state.attributes[plant.READING_BRIGHTNESS])

    def test_load_from_db(self):
        init_recorder_component(self.hass)
        plant_name = 'wise_plant'
        for value in [20, 30, 10]:

            self.hass.states.set(BRIGHTNESS_ENTITIY, value,
                                 {ATTR_UNIT_OF_MEASUREMENT: 'Lux'})
            self.hass.block_till_done()
        # wait for the recorder to really store the data
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()
        assert setup_component(self.hass, plant.DOMAIN, {
            plant.DOMAIN: {
                plant_name: GOOD_CONFIG
            }
        })
        self.hass.block_till_done()

        state = self.hass.states.get('plant.'+plant_name)
        self.assertEquals(STATE_UNKNOWN, state.state)
        max_brightness = state.attributes.get(
            plant.ATTR_MAX_BRIGHTNESS_HISTORY)
        self.assertEquals(30, max_brightness)


class TestDailyHistory(unittest.TestCase):

    def test_no_data(self):
        dh = plant.DailyHistory(3)
        self.assertIsNone(dh.max)

    def test_one_day(self):
        dh = plant.DailyHistory(3)
        values = [-2, 10, 0, 5, 20]
        for i in range(len(values)):
            dh.add_measurement(values[i])
            max_value = max(values[0:i+1])
            self.assertEqual(1, len(dh._days))
            self.assertEqual(dh.max, max_value)

    def test_multiple_days(self):
        dh = plant.DailyHistory(3)
        today = datetime.now()
        today_minus_1 = today - timedelta(days=1)
        today_minus_2 = today_minus_1 - timedelta(days=1)
        today_minus_3 = today_minus_2 - timedelta(days=1)
        days = [today_minus_3, today_minus_2, today_minus_1, today]
        values = [10, 1, 7, 3]
        max_values = [10, 10, 10, 7]

        for i in range(len(days)):
            dh.add_measurement(values[i], days[i])
            self.assertEquals(max_values[i], dh.max)
