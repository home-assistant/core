"""
Support for Qwikswitch Relays and Dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.qwikswitch/
"""
from homeassistant.components.qwikswitch import (
    QSToggleEntity, DOMAIN as QWIKSWITCH)
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light

DEPENDENCIES = [QWIKSWITCH]


async def async_setup_platform(hass, _, add_devices, discovery_info=None):
    """Add lights from the main Qwikswitch component."""
    qsusb = hass.data[QWIKSWITCH]
    devs = [QSLight(id, qsusb) for id in discovery_info[QWIKSWITCH]]

    add_devices(devs)

    for _id, dev in zip(discovery_info[QWIKSWITCH], devs):
        hass.helpers.dispatcher.async_dispatcher_connect(
            _id, dev.schedule_update_ha_state)  # Part of Entity/ToggleEntity


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

    @property
    def brightness(self):
        """Return the brightness of this light (0-255)."""
        return self._qsusb[self._id, 1] if self._dim else None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS if self._dim else 0
