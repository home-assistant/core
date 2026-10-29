"""Services for the Wake on LAN integration."""

from functools import partial
import logging

import probatio
import wakeonlan

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_SECUREON_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MAC): cv.string,
        probatio.Optional(probatio.Secret(CONF_SECUREON_PASSWORD)): cv.string,
        probatio.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        probatio.Optional(CONF_BROADCAST_PORT): probatio.Port(),
    }
)


async def _send_magic_packet(call: ServiceCall) -> None:
    """Send magic packet to wake up a device."""
    hass = call.hass
    mac_address: str = call.data[CONF_MAC]
    secureon_password = call.data.get(CONF_SECUREON_PASSWORD)
    broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
    broadcast_port = call.data.get(CONF_BROADCAST_PORT)

    service_kwargs = {}
    if broadcast_address is not None:
        service_kwargs["ip_address"] = broadcast_address
    if broadcast_port is not None:
        service_kwargs["port"] = broadcast_port

    _LOGGER.debug(
        "Send magic packet to mac %s (secureon: %s, broadcast: %s, port: %s)",
        mac_address,
        secureon_password is not None,
        broadcast_address,
        broadcast_port,
    )

    if secureon_password:
        mac_address += f"/{secureon_password}"

    await hass.async_add_executor_job(
        partial(wakeonlan.send_magic_packet, mac_address, **service_kwargs)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Wake on LAN integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        _send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )
