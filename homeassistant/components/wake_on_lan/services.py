"""Services for the Wake on LAN integration."""

from enum import StrEnum
from functools import partial
import logging

import probatio
import wakeonlan

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WakeOnLanService(StrEnum):
    """Store keys for Wake on LAN services."""

    SEND_MAGIC_PACKET = "send_magic_packet"


class WakeOnLanServiceArgument(StrEnum):
    """Store keys for Wake on LAN service arguments."""

    MAC = "mac"
    SECUREON_PASSWORD = "secureon_password"
    BROADCAST_ADDRESS = "broadcast_address"
    BROADCAST_PORT = "broadcast_port"


WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = probatio.Schema(
    {
        probatio.Required(WakeOnLanServiceArgument.MAC): cv.string,
        probatio.Optional(
            probatio.Secret(WakeOnLanServiceArgument.SECUREON_PASSWORD)
        ): cv.string,
        probatio.Optional(WakeOnLanServiceArgument.BROADCAST_ADDRESS): cv.string,
        probatio.Optional(WakeOnLanServiceArgument.BROADCAST_PORT): probatio.Port(),
    }
)


async def _send_magic_packet(call: ServiceCall) -> None:
    """Send magic packet to wake up a device."""
    hass = call.hass
    mac_address: str = call.data[WakeOnLanServiceArgument.MAC]
    secureon_password = call.data.get(WakeOnLanServiceArgument.SECUREON_PASSWORD)
    broadcast_address = call.data.get(WakeOnLanServiceArgument.BROADCAST_ADDRESS)
    broadcast_port = call.data.get(WakeOnLanServiceArgument.BROADCAST_PORT)

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
        WakeOnLanService.SEND_MAGIC_PACKET,
        _send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )
