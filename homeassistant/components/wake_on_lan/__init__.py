"""Support for sending Wake-On-LAN magic packets."""
from functools import partial
import logging

import voluptuous as vol
import wakeonlan

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_MAC
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wake_on_lan"

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema(
    {vol.Required(CONF_MAC): cv.string, vol.Optional(CONF_BROADCAST_ADDRESS): cv.string}
)


async def async_setup(hass, config):
    """Set up the wake on LAN component."""

    async def send_magic_packet(call):
        """Send magic packet to wake up a device."""
        mac_address = call.data.get(CONF_MAC)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        _LOGGER.info(
            "Send magic packet to mac %s (broadcast: %s)",
            mac_address,
            broadcast_address,
        )
        if broadcast_address is not None:
            await hass.async_add_job(
                partial(
                    wakeonlan.send_magic_packet,
                    mac_address,
                    ip_address=broadcast_address,
                )
            )
        else:
            await hass.async_add_job(partial(wakeonlan.send_magic_packet, mac_address))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    return True
