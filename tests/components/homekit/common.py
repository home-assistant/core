"""Collection of fixtures and functions for the HomeKit tests."""
from unittest.mock import patch

import pytest

from pyhap.accessory_driver import AccessoryDriver


@pytest.fixture(scope='session')
def hk_driver():
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch('pyhap.accessory_driver.Zeroconf'), \
        patch('pyhap.accessory_driver.AccessoryEncoder'), \
        patch('pyhap.accessory_driver.HAPServer'), \
            patch('pyhap.accessory_driver.AccessoryDriver.publish'):
        return AccessoryDriver(pincode=b'123-45-678')


def patch_debounce():
    """Return patch for debounce method."""
    return patch('homeassistant.components.homekit.accessories.debounce',
                 lambda f: lambda *args, **kwargs: f(*args, **kwargs))
