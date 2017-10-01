"""The tests for the hue sensors platform."""

import requests_mock
import unittest

from homeassistant.components.sensor.hue import (
    HueSensorData, HueSensor)
from tests.common import load_fixture, get_test_home_assistant


class TestHueSensor(unittest.TestCase):
    """Test the Hue sensors platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_hue_sensors(self, mock_req):
        """Test for hue_sensors."""
        with requests_mock.mock() as mock_req:
            mock_url = 'http://mock'
            mock_req.get(mock_url, text=load_fixture('hue_sensors.json'))
            data = HueSensorData(mock_url)
            data.update()
            sensors = []
            for key in data.data.keys():
                sensor = HueSensor(key, data)
                sensor.update()
                sensors.append(sensor)
            assert len(sensors) == 6
            for sensor in sensors:
                if sensor.name == 'Living room motion sensor':
                    assert sensor.state is 'off'
                    assert sensor.device_state_attributes[
                        'light_level'] == 0
                    assert sensor.device_state_attributes[
                        'temperature'] == 21.38
                elif sensor.name == 'Living room remote':
                    assert sensor.state == '1_hold'
                    assert sensor.device_state_attributes[
                        'last updated'] == ['2017-09-15', '16:35:00']
                elif sensor.name == 'Robins iPhone':
                    assert sensor.state is 'on'
                else:
                    assert sensor.name in [
                        'Bedroom motion sensor',
                        'Remote bedroom',
                        'Hall motion Sensor']
