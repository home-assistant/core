"""The tests for Efergy sensor platform."""
import unittest

import requests_mock

from homeassistant.components.sensor import efergy

from tests.common import load_fixture, get_test_home_assistant

ONE_SENSOR_CONFIG = {
    'platform': 'efergy',
    'app_token': '9p6QGJ7dpZfO3fqPTBk1fyEmjV1cGoLT',
    'utc_offset': '300',
    'monitored_variables': [{'type': 'amount', 'period': 'day',
                             'currency': '$'},
                            {'type': 'instant_readings', 'period': 'day',
                             'currency': '$'},
                            {'type':  'budget', 'period': 'day',
                             'currency': '$'},
                            {'type': 'cost', 'period': 'day', 'currency': '$'}
                            ]
}


def mock_responses(mock):
    """Mock responses for Efergy."""
    base_url = 'https://engage.efergy.com/mobile_proxy/'
    token = '9p6QGJ7dpZfO3fqPTBk1fyEmjV1cGoLT'
    mock.get(
        base_url + 'getInstant?token=' + token,
        text=load_fixture('efergy_instant.json'))
    mock.get(
        base_url + 'getEnergy?token=' + token + '&offset=300&period=day',
        text=load_fixture('efergy_energy.json'))
    mock.get(
        base_url + 'getBudget?token=' + token,
        text=load_fixture('efergy_budget.json'))
    mock.get(
        base_url + 'getCost?token=' + token + '&offset=300&period=day',
        text=load_fixture('efergy_cost.json'))


class TestEfergySensor(unittest.TestCase):
    """Tests the Efergy Sensor platform."""

    DEVICES = []

    @requests_mock.Mocker()
    def add_devices(self, devices, mock):
        """Mock add devices."""
        mock_responses(mock)
        for device in devices:
            device.update()
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = ONE_SENSOR_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for successfully setting up the Efergy platform."""
        mock_responses(mock)

        efergy.setup_platform(self.hass,
                              self.config,
                              self.add_devices)
        self.assertEqual(4, len(self.DEVICES))

    @requests_mock.Mocker()
    def test_single_sensor_readings(self, mock):
        """Test the reading of the instant value."""
        energy_reading = self.DEVICES[0]
        instant_reading = self.DEVICES[1]
        budget_reading = self.DEVICES[2]
        cost_reading = self.DEVICES[3]
        self.assertEqual('38.21', energy_reading.state)
        self.assertEqual(1.58, instant_reading.state)
        self.assertEqual('ok', budget_reading.state)
        self.assertEqual('5.27', cost_reading.state)
