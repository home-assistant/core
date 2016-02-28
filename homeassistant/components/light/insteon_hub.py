"""
homeassistant.components.light.insteon
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Insteon Hub lights.
"""

from homeassistant.components.insteon_hub import INSTEON, InsteonToggleDevice


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Insteon Hub light platform. """
    devs = []
    for device in INSTEON.devices:
        if device.DeviceCategory == "Switched Lighting Control":
            devs.append(InsteonToggleDevice(device))
        if device.DeviceCategory == "Dimmable Lighting Control":
            devs.append(InsteonToggleDevice(device))
    add_devices(devs)
