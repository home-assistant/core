"""The Voice over IP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from voip_utils import SIP_PORT

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .voip import HassVoipDatagramProtocol

_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VoIP integration from a config entry."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    _LOGGER.debug(
        "Listening for VoIP calls from %s (port=%s)",
        ip_address,
        SIP_PORT,
    )
    hass.data[DOMAIN] = await _create_sip_server(
        hass,
        lambda: HassVoipDatagramProtocol(hass, {str(ip_address)}),
    )

    return True


async def _create_sip_server(
    hass: HomeAssistant,
    protocol_factory: Callable[
        [],
        asyncio.DatagramProtocol,
    ],
) -> asyncio.DatagramTransport:
    transport, _protocol = await hass.loop.create_datagram_endpoint(
        protocol_factory,
        local_addr=(_IP_WILDCARD, SIP_PORT),
    )

    return transport


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload VoIP."""
    transport = hass.data.pop(DOMAIN, None)
    if transport is not None:
        transport.close()
        _LOGGER.debug("Shut down VoIP server")

    return True
