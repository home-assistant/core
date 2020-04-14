"""Collection of fixtures and functions for the HomeKit tests."""
from unittest.mock import patch

from pyhap.accessory_driver import AccessoryDriver
import pytest


def patch_debounce():
    """Return patch for debounce method."""
    return patch(
        "homeassistant.components.homekit.accessories.debounce",
        lambda f: lambda *args, **kwargs: f(*args, **kwargs),
    )


@pytest.fixture
def driver():
    """Patch AccessoryDriver without zeroconf or HAPServer."""
    with patch("pyhap.accessory_driver.HAPServer"), patch(
        "pyhap.accessory_driver.Zeroconf"
    ), patch("pyhap.accessory_driver.AccessoryDriver.persist"):
        yield AccessoryDriver()
