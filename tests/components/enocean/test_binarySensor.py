"""Tests for emulated_roku library bindings."""
import unittest

from enocean.protocol.constants import PACKET
from enocean.protocol.packet import RadioPacket

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE_DOOR,
    DEVICE_CLASS_WINDOW,
    DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.enocean.binary_sensor import EnOceanBinarySensor

from tests.common import get_test_home_assistant


class TestEnOceanBinarySensor(unittest.TestCase):
    """Unit tests for the ENOcean binary sensors."""

    def setUp(self):
        """Set up test data."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Tear down unit test data."""
        self.hass.stop()

    def create_test_sensor(self, type, initial_state):
        """Create a sensor using the test hass instance, and with a given initial state."""
        sensor = EnOceanBinarySensor("device ID", "device name", type)
        sensor.hass = self.hass
        sensor.onoff = initial_state
        return sensor

    def create_packet(self, is_opened):
        """Create an ENOcean 1BS packet with provided status."""
        payload = 0x08 if is_opened else 0x09
        return RadioPacket(
            PACKET.RADIO,
            data=[0xD5, payload, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
        )

    def test_1BS_close_frame_sets_generic_sensor_to_on(self):
        """Test generic sensor state after receiving a close frame."""

        # prepare
        sensor = self.create_test_sensor(DEVICE_CLASSES_SCHEMA, 0)
        packet = self.create_packet(is_opened=False)

        # execute
        sensor.value_changed(packet)

        # assert
        assert sensor.is_on is True

    def test_1BS_open_frame_sets_generic_sensor_to_off(self):
        """Test generic sensor state after receiving an open frame."""

        # prepare
        sensor = self.create_test_sensor(DEVICE_CLASSES_SCHEMA, 1)
        packet = self.create_packet(is_opened=True)

        # execute
        sensor.value_changed(packet)

        # assert
        assert sensor.is_on is False

    def test_1BS_close_frame_sets_window_door_garage_sensor_to_off(self):
        """Test door, window of garage door sensor state after receiving a close frame."""

        # prepare
        window_sensor = self.create_test_sensor(DEVICE_CLASS_WINDOW, 1)
        door_sensor = self.create_test_sensor(DEVICE_CLASS_DOOR, 1)
        garage_sensor = self.create_test_sensor(DEVICE_CLASS_GARAGE_DOOR, 1)
        packet = self.create_packet(is_opened=False)

        # execute
        window_sensor.value_changed(packet)
        door_sensor.value_changed(packet)
        garage_sensor.value_changed(packet)

        # assert
        assert window_sensor.is_on is False
        assert door_sensor.is_on is False
        assert garage_sensor.is_on is False

    def test_1BS_open_frame_sets_window_door_garage_sensor_to_on(self):
        """Test door, window of garage door sensor state after receiving an open frame."""

        # prepare
        window_sensor = self.create_test_sensor(DEVICE_CLASS_WINDOW, 0)
        door_sensor = self.create_test_sensor(DEVICE_CLASS_DOOR, 0)
        garage_sensor = self.create_test_sensor(DEVICE_CLASS_GARAGE_DOOR, 0)
        packet = self.create_packet(is_opened=True)

        # execute
        window_sensor.value_changed(packet)
        door_sensor.value_changed(packet)
        garage_sensor.value_changed(packet)

        # assert
        assert window_sensor.is_on is True
        assert door_sensor.is_on is True
        assert garage_sensor.is_on is True
