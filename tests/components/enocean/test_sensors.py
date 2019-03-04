"""Test sensor implementations."""
import unittest
from unittest.mock import patch, MagicMock

from enocean.protocol.packet import RadioPacket

from homeassistant.components import enocean as enocean_component
from homeassistant.components.enocean import sensor
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)


class TestEnOceanTemperatureSensor(unittest.TestCase):
    """Verify that the temperature sensor can understand EnOcean packets."""

    @staticmethod
    def is_about_right(expected, actual, tolerance=0.1):
        """Verify that a number is close enough to be considered correct.

        This check concedes that the temperature value resolutions are limited
        and cannot represent all values. This is not a bug, but simply a
        limitation of the protocols number scale.
        """
        return expected - tolerance <= actual <= expected + tolerance

    def setUp(self):
        """Set up things to be run when tests are started."""
        enocean_component.ENOCEAN_DONGLE = MagicMock()
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name', 0.0,
                                                      40.0, 255, 0)

    def test_setup(self):
        """Test sensor initialization."""
        assert self.device.name == 'Temperature sensor name'
        assert self.device.unit_of_measurement == TEMP_CELSIUS
        assert self.device.device_class == DEVICE_CLASS_TEMPERATURE
        assert self.device.state is None
        assert self.device.dev_id == 'id'

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_packet_min(self, mock_update):
        """Test packet at minimum temperature of EEP A5-02-05."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x05,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=0)
        self.device.value_changed(pkg)
        assert self.device.state == 0
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_packet_max(self, mock_update):
        """Test packet at maximum temperature of EEP A5-02-05."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x05,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=40.0)
        self.device.value_changed(pkg)
        assert self.device.state == 40.0
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_mid_packet(self, mock_update):
        """Test packet at mid temperature of EEP A5-02-05."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x05,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=18.8)
        self.device.value_changed(pkg)
        assert self.device.state == 18.8
        assert self.is_about_right(18.8, self.device.state)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_02_01(self, mock_update):
        """Test that it can handle EEP A5-02-01."""
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      -40.0, 0.0, 255, 0)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=-21.4)
        self.device.value_changed(pkg)
        assert self.is_about_right(-21.4, self.device.state)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_02_02_to_04(self, mock_update):
        """Test that it can handle EEP A5-02-02 to A5-02-04.

        Both profiles cover negative and positive temperatures.
        """
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      -30.0, 10.0, 255, 0)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x02,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=-5.4)
        self.device.value_changed(pkg)
        assert self.is_about_right(-5.4, self.device.state)

        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x02,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=5.4)
        self.device.value_changed(pkg)
        assert self.is_about_right(5.4, self.device.state)
        assert mock_update.call_count == 2

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_02_05(self, mock_update):
        """Test that it can handle EEP A5-02-05."""
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      0.0, 40.0, 255, 0)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x05,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=5.4)
        self.device.value_changed(pkg)
        assert self.is_about_right(5.4, self.device.state)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_02_06_to_0b(self, mock_update):
        """Test that it can handle EEP A5-02-06 to EEP A5-02-0B.

        These are all positive numbered and have a range of 40.
        """
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      10.0, 50.0, 255, 0)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x06,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=44.4)
        self.device.value_changed(pkg)
        assert self.is_about_right(44.4, self.device.state)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_02_10(self, mock_update):
        """Test that it can handle EEP A5-02-10.

        Presumably it can also handle all other profiles with a range different
        from 40. Bigger ranges have increased step size and the inaccuracy.
        """
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      -60.0, 20.0, 255, 0)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x02, rorg_type=0x10,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], TMP=-50.0)
        self.device.value_changed(pkg)
        assert self.is_about_right(-50.0, self.device.state, 0.4)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_04_01(self, mock_update):
        """Test that it can handle EEP A5-04-01.

        Contains temperature and humidity data, but the range is inverted.
        """
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name',
                                                      0.0, 40.0, 0, 250)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x04, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 TMP=5.0, HUM=20.0)
        self.device.value_changed(pkg)
        assert self.is_about_right(5.0, self.device.state)
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanTemperatureSensor, 'schedule_update_ha_state')
    def test_eep_a5_10_10(self, mock_update):
        """Test that it can handle Room Operating Panels."""
        self.device = sensor.EnOceanTemperatureSensor('id', 'sensor name', 0.0,
                                                      40.0, 0, 250)
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x10, rorg_type=0x12,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 TMP=5.0, HUM=20.0)
        self.device.value_changed(pkg)
        assert self.is_about_right(5.0, self.device.state)
        assert mock_update.call_count == 1


class TestEnOceanHumiditySensor(unittest.TestCase):
    """Verify that the humidity sensor can understand EnOcean packets."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        enocean_component.ENOCEAN_DONGLE = MagicMock()
        self.device = sensor.EnOceanHumiditySensor('id', 'sensor name')

    def test_setup(self):
        """Test sensor initialization."""
        assert self.device.name == 'Humidity sensor name'
        assert self.device.unit_of_measurement == \
            sensor.SENSOR_TYPES[DEVICE_CLASS_HUMIDITY]['unit']
        assert self.device.device_class == DEVICE_CLASS_HUMIDITY
        assert self.device.state is None

    @patch.object(sensor.EnOceanHumiditySensor, 'schedule_update_ha_state')
    def test_eep_a5_04_01(self, mock_update):
        """Test that it can handle EEP A5-04-01."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x04, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 TMP=5.0, HUM=20.0)
        self.device.value_changed(pkg)
        assert self.device.state == 20
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanHumiditySensor, 'schedule_update_ha_state')
    def test_eep_a5_10_10(self, mock_update):
        """Test that it can handle Room Operating Panels."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x10, rorg_type=0x12,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 TMP=5.0, HUM=20.0)
        self.device.value_changed(pkg)
        assert self.device.state == 20
        assert mock_update.call_count == 1


class TestEnOceanPowerSensor(unittest.TestCase):
    """Verify that the power sensor can understand EnOcean packets."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        enocean_component.ENOCEAN_DONGLE = MagicMock()
        self.device = sensor.EnOceanPowerSensor('id', 'sensor name')

    def test_setup(self):
        """Test sensor initialization."""
        assert self.device.name == 'Power sensor name'
        assert self.device.unit_of_measurement == \
            sensor.SENSOR_TYPES[sensor.DEVICE_CLASS_POWER]['unit']
        assert self.device.device_class == sensor.DEVICE_CLASS_POWER
        assert self.device.state is None

    @patch.object(sensor.EnOceanPowerSensor, 'schedule_update_ha_state')
    def test_eep_a5_12_01_div0(self, mock_update):
        """Test that it can handle EEP A5-12-01 at divisor 1."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x12, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 MR=123, DT=1, DIV=0)
        self.device.value_changed(pkg)
        assert self.device.state == 123.0
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanPowerSensor, 'schedule_update_ha_state')
    def test_eep_a5_12_01_div2(self, mock_update):
        """Test that it can handle EEP A5-12-01 at divisor 100."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x12, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 MR=123, DT=1, DIV=2)
        self.device.value_changed(pkg)
        assert self.device.state == 1.23
        assert mock_update.call_count == 1

    @patch.object(sensor.EnOceanPowerSensor, 'schedule_update_ha_state')
    def test_cumulative_value(self, mock_update):
        """Test that it ignores cumulative values."""
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x12, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 MR=123, DT=0, DIV=2)
        self.device.value_changed(pkg)
        assert self.device.state is None
        assert mock_update.call_count == 0
