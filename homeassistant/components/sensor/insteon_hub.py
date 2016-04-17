"""
Support for Insteon Hub lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
from homeassistant.components.insteon_hub import (
    INSTEON,
    InsteonSensorDevice,
    filter_devices
)

DEVICE_CATEGORIES = [{
    'DevCat': 16,
    'SubCat': [1]}]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon Hub light platform."""
    devs = []
    for device in filter_devices(INSTEON.devices, DEVICE_CATEGORIES):
        devs.append(InsteonSensorDevice(device))
    add_devices(devs)
