"""HomeKit session fixtures."""
from unittest.mock import patch

from pyhap.accessory_driver import AccessoryDriver
import pytest

from homeassistant.components.homekit.const import EVENT_HOMEKIT_CHANGED

from tests.common import async_capture_events


@pytest.fixture
def hk_driver(loop):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.Zeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer.async_stop"), patch(
        "pyhap.accessory_driver.HAPServer.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist"
    ):
        yield AccessoryDriver(pincode=b"123-45-678", address="127.0.0.1", loop=loop)


@pytest.fixture
def events(hass):
    """Yield caught homekit_changed events."""
    return async_capture_events(hass, EVENT_HOMEKIT_CHANGED)
