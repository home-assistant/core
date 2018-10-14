"""HomeKit session fixtures."""
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
        return AccessoryDriver(pincode=b'123-45-678', address='127.0.0.1')
