"""Support for Qwikswitch relays."""
from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as QWIKSWITCH, QSToggleEntity


async def async_setup_platform(hass, _, add_entities, discovery_info=None):
    """Add switches from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    devs = [QSSwitch(qsid, qsusb) for qsid in discovery_info[QWIKSWITCH]]
    add_entities(devs)


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""
