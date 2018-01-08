"""
Component to wake up devices sending Wake-On-LAN magic packets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wake_on_lan/
"""
import asyncio
from functools import partial
import logging

import voluptuous as vol

from homeassistant.const import CONF_MAC
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['wakeonlan==0.2.2']

DOMAIN = "wake_on_lan"
_LOGGER = logging.getLogger(__name__)

CONF_BROADCAST_ADDRESS = 'broadcast_address'

SERVICE_SEND_MAGIC_PACKET = 'send_magic_packet'

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the wake on LAN component."""
    from wakeonlan import wol

    @asyncio.coroutine
    def send_magic_packet(call):
        """Send magic packet to wake up a device."""
        mac_address = call.data.get(CONF_MAC)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        _LOGGER.info("Send magic packet to mac %s (broadcast: %s)",
                     mac_address, broadcast_address)
        if broadcast_address is not None:
            yield from hass.async_add_job(
                partial(wol.send_magic_packet, mac_address,
                        ip_address=broadcast_address))
        else:
            yield from hass.async_add_job(
                partial(wol.send_magic_packet, mac_address))

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MAGIC_PACKET, send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA)

    return True
