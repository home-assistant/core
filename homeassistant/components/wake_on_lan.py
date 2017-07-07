"""
Component to wake up devices sending Wake-On-LAN magic packets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wake_on_lan/
"""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import CONF_MAC
from homeassistant.core import callback
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

    @callback
    def send_magic_packet(call):
        """Send magic packet to wake up a device."""
        mac_address = call.data.get(CONF_MAC)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        _LOGGER.info("Send magic packet to mac %s (broadcast: %s)",
                     mac_address, broadcast_address)
        if broadcast_address is not None:
            wol.send_magic_packet(mac_address, ip_address=broadcast_address)
        else:
            wol.send_magic_packet(mac_address)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MAGIC_PACKET, send_magic_packet,
        description=descriptions.get(DOMAIN).get(SERVICE_SEND_MAGIC_PACKET),
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA)

    _LOGGER.debug("Set up of WOL service done.")
    return True
