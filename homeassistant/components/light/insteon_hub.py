"""
Support for Insteon Hub lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
from homeassistant.components.insteon_hub import (INSTEON, InsteonToggleDevice, filter)

DEVICE_CATEGORIES = [{
    'DevCat': 1,
    'SubCat': [46]}]
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon Hub light platform."""
    devs = []
    for device in filter(INSTEON.devices, DEVICE_CATEGORIES):
        devs.append(InsteonToggleDevice(device))
    add_devices(devs)
