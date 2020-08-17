"""Tests for Belkin WeMo switch."""
import pytest

from homeassistant.components.wemo import switch

from . import ConfigEntryTests, DeviceTests, SubscriptionTests


@pytest.fixture
def wemo_device(pywemo_device):
    """Create a device for the WemoSwitch."""
    return switch.WemoSwitch(pywemo_device)


class TestWemoSwitch(ConfigEntryTests, DeviceTests, SubscriptionTests):
    """Tests for the switch.WemoSwitch."""

    DEVICE_MODEL = "LightSwitch"
