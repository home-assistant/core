"""Unit tests for platform/plant.py."""
import asyncio

import homeassistant.components.plant as plant


GOOD_DATA = {
    'moisture': 50,
    'battery': 90,
    'temperature': 23.4,
    'conductivity': 777,
    'brightness': 987,
}

GOOD_CONFIG = {
    'sensors': {
        'moisture': 'sensor.mqtt_plant_moisture',
        'battery': 'sensor.mqtt_plant_battery',
        'temperature': 'sensor.mqtt_plant_temperature',
        'conductivity': 'sensor.mqtt_plant_conductivity',
        'brightness': 'sensor.mqtt_plant_brightness',
    },
    'min_moisture': 20,
    'max_moisture': 60,
    'min_battery': 17,
    'min_conductivity': 500,
    'min_temperature': 15,
}


class _MockState(object):

    def __init__(self, state=None):
        self.state = state


@asyncio.coroutine
def test_valid_data(hass):
    """Test processing valid data."""
    sensor = plant.Plant('my plant', GOOD_CONFIG)
    sensor.hass = hass
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
def test_low_battery(hass):
    """Test processing with low battery data and limit set."""
    sensor = plant.Plant(hass, GOOD_CONFIG)
    sensor.hass = hass
    assert sensor.state_attributes['problem'] == 'none'
    sensor.state_changed('sensor.mqtt_plant_battery',
                         _MockState(45), _MockState(10))
    assert sensor.state == 'problem'
    assert sensor.state_attributes['problem'] == 'battery low'
