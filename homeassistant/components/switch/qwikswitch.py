"""
Support for Qwikswitch relays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.qwikswitch/
"""
from homeassistant.components.qwikswitch import (
    QSToggleEntity, DOMAIN as QWIKSWITCH)
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = [QWIKSWITCH]


async def async_setup_platform(hass, _, add_devices, discovery_info=None):
    """Add switches from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    devs = [QSSwitch(qsid, qsusb) for qsid in discovery_info[QWIKSWITCH]]
    add_devices(devs)


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""
