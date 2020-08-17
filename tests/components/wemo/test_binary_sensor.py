"""Tests for Belkin WeMo binary_sensor."""
import pytest

from homeassistant.components.wemo import binary_sensor

from . import ConfigEntryTests, DeviceTests, SubscriptionTests


@pytest.fixture
def wemo_device(pywemo_device):
    """Create a device for the WemoBinarySensor."""
    return binary_sensor.WemoBinarySensor(pywemo_device)


class TestWemoBinarySensor(ConfigEntryTests, DeviceTests, SubscriptionTests):
    """Tests for the binary_sensor.WemoBinarySensor."""

    DEVICE_MODEL = "Motion"
