"""Support for sending Wake-On-LAN magic packets."""
from functools import partial
import logging

import voluptuous as vol
import wakeonlan

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wake_on_lan"

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
    }
)


async def async_setup(hass, config):
    """Set up the wake on LAN component."""

    async def send_magic_packet(call):
        """Send magic packet to wake up a device."""
        mac_address = call.data.get(CONF_MAC)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        broadcast_port = call.data.get(CONF_BROADCAST_PORT)

        service_kwargs = {}
        if broadcast_address is not None:
            service_kwargs["ip_address"] = broadcast_address
        if broadcast_port is not None:
            service_kwargs["port"] = broadcast_port

        _LOGGER.info(
            "Send magic packet to mac %s (broadcast: %s, port: %s)",
            mac_address,
            broadcast_address,
            broadcast_port,
        )

        await hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, mac_address, **service_kwargs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    return True
