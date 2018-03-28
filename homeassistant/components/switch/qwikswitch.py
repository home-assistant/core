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
    qsusb = hass.data[QWIKSWITCH]
    devs = [QSSwitch(id, qsusb) for id in discovery_info[QWIKSWITCH]]

    add_devices(devs)

    for _id, dev in zip(discovery_info[QWIKSWITCH], devs):
        hass.helpers.dispatcher.async_dispatcher_connect(
            _id, dev.schedule_update_ha_state)


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""

    pass
