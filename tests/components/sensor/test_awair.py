"""Tests for the Awair sensor platform."""

from datetime import datetime
import unittest
from unittest import mock

from homeassistant.components.sensor import awair

FAKE_UUID = 'awair_12345'
SCORE = 82
TIMESTAMP = datetime.strptime('2018-11-19T00:53:58.458Z', awair.TIME_FORMAT)


class FakeAwairSensor(awair.AwairSensor):
    """A fake Awair Sensor."""


class FakeAwairData(awair.AwairData):
    """Made-up Awair data."""

    def __init__(self, client, uuid):
        """Initialize the object."""
        awair.AwairData.__init__(self, client, uuid)

        self.data = {
            awair.ATTR_TIMESTAMP: TIMESTAMP,
            awair.ATTR_SCORE: SCORE,
            'TEMP': 21.69,
            'HUMID': 37.85,
            'CO2': 769,
            'VOC': 821,
            'DUST': 5.7,
        }


class TestAwair(unittest.TestCase):
    """Test the Awair class."""

    def setUp(self):
        """Configure a new fake device and datasource."""
        self.client = mock.MagicMock()
        self.data = FakeAwairData(self.client, FAKE_UUID)
        device = {
            awair.CONF_UUID: FAKE_UUID,
        }

        self.awair_sensors = {
            'TEMP': None,
            'HUMID': None,
            'CO2': None,
            'VOC': None,
            'DUST': None,
        }

        for sensor in self.awair_sensors:
            fake_sensor = FakeAwairSensor(self.data, device, sensor)
            self.awair_sensors[sensor] = fake_sensor

    def test_name(self):
        """Ensure the name is set correctly."""
        name = self.awair_sensors['DUST'].name
        device_class = awair.SENSOR_TYPES['DUST']['device_class']
        assert name == 'Awair {}'.format(device_class)

    def test_device_class(self):
        """Ensure the device_class is set correctly."""
        dc1 = self.awair_sensors['TEMP'].device_class
        dc2 = awair.SENSOR_TYPES['TEMP']['device_class']
        assert dc1 == dc2

    def test_state(self):
        """Ensure we get a valid state object."""
        state = self.awair_sensors['CO2'].state
        assert state == 769

    def test_score(self):
        """Ensure score is set."""
        assert self.awair_sensors['CO2'].score == SCORE

    def test_timestamp(self):
        """Ensure timestamp is set."""
        assert self.awair_sensors['HUMID'].timestamp == TIMESTAMP

    def test_unique_id(self):
        """Ensure unique id is set correctly."""
        sensor = self.awair_sensors['CO2']
        assert sensor.unique_id == 'awair_12345_CO2'

    def test_unit_of_measurement(self):
        """Ensure unit of measurement is right."""
        unit_one = self.awair_sensors['DUST'].unit_of_measurement
        unit_two = awair.SENSOR_TYPES['DUST']['unit_of_measurement']
        assert unit_one == unit_two

    async def test_async_update_delegates(self):
        """Ensure async update delegates to data component."""
        await self.awair_sensors['CO2'].async_update()
        assert self.client.async_update.call_count == 1
