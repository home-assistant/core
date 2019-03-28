"""
Support for Qwikswitch Relays and Dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.qwikswitch/
"""
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light

from . import DOMAIN as QWIKSWITCH, QSToggleEntity

DEPENDENCIES = [QWIKSWITCH]


async def async_setup_platform(hass, _, add_entities, discovery_info=None):
    """Add lights from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    devs = [QSLight(qsid, qsusb) for qsid in discovery_info[QWIKSWITCH]]
    add_entities(devs)


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

    @property
    def brightness(self):
        """Return the brightness of this light (0-255)."""
        return self.device.value if self.device.is_dimmer else None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS if self.device.is_dimmer else 0
