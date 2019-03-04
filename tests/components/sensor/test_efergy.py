"""The tests for Efergy sensor platform."""
import unittest

import requests_mock

from homeassistant.setup import setup_component

from tests.common import load_fixture, get_test_home_assistant

token = '9p6QGJ7dpZfO3fqPTBk1fyEmjV1cGoLT'
multi_sensor_token = '9r6QGF7dpZfO3fqPTBl1fyRmjV1cGoLT'

ONE_SENSOR_CONFIG = {
    'platform': 'efergy',
    'app_token': token,
    'utc_offset': '300',
    'monitored_variables': [
        {'type': 'amount', 'period': 'day'},
        {'type': 'instant_readings'},
        {'type': 'budget'},
        {'type': 'cost', 'period': 'day', 'currency': '$'},
        {'type': 'current_values'},
    ]
}

MULTI_SENSOR_CONFIG = {
    'platform': 'efergy',
    'app_token': multi_sensor_token,
    'utc_offset': '300',
    'monitored_variables': [{'type': 'current_values'}],
}


def mock_responses(mock):
    """Mock responses for Efergy."""
    base_url = 'https://engage.efergy.com/mobile_proxy/'
    mock.get(
        '{}getInstant?token={}'.format(base_url, token),
        text=load_fixture('efergy_instant.json'))
    mock.get(
        '{}getEnergy?token={}&offset=300&period=day'.format(base_url, token),
        text=load_fixture('efergy_energy.json'))
    mock.get(
        '{}getBudget?token={}'.format(base_url, token),
        text=load_fixture('efergy_budget.json'))
    mock.get(
        '{}getCost?token={}&offset=300&period=day'.format(base_url, token),
        text=load_fixture('efergy_cost.json'))
    mock.get(
        '{}getCurrentValuesSummary?token={}'.format(base_url, token),
        text=load_fixture('efergy_current_values_single.json'))
    mock.get(
        '{}getCurrentValuesSummary?token={}'.format(
            base_url, multi_sensor_token),
        text=load_fixture('efergy_current_values_multi.json'))


class TestEfergySensor(unittest.TestCase):
    """Tests the Efergy Sensor platform."""

    DEVICES = []

    @requests_mock.Mocker()
    def add_entities(self, devices, mock):
        """Mock add devices."""
        mock_responses(mock)
        for device in devices:
            device.update()
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = ONE_SENSOR_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_single_sensor_readings(self, mock):
        """Test for successfully setting up the Efergy platform."""
        mock_responses(mock)
        assert setup_component(self.hass, 'sensor', {
            'sensor': ONE_SENSOR_CONFIG,
        })

        assert '38.21' == self.hass.states.get('sensor.energy_consumed').state
        assert '1580' == self.hass.states.get('sensor.energy_usage').state
        assert 'ok' == self.hass.states.get('sensor.energy_budget').state
        assert '5.27' == self.hass.states.get('sensor.energy_cost').state
        assert '1628' == self.hass.states.get('sensor.efergy_728386').state

    @requests_mock.Mocker()
    def test_multi_sensor_readings(self, mock):
        """Test for multiple sensors in one household."""
        mock_responses(mock)
        assert setup_component(self.hass, 'sensor', {
            'sensor': MULTI_SENSOR_CONFIG,
        })

        assert '218' == self.hass.states.get('sensor.efergy_728386').state
        assert '1808' == self.hass.states.get('sensor.efergy_0').state
        assert '312' == self.hass.states.get('sensor.efergy_728387').state
