"""The Voice over IP integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sip import SIP_PORT
from .voip import VoipDatagramProtocol

_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VoIP integration from a config entry."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    _LOGGER.debug(
        "Listening for VoIP calls from %s (port=%s)",
        ip_address,
        SIP_PORT,
    )
    transport, _protocol = await hass.loop.create_datagram_endpoint(
        lambda: VoipDatagramProtocol(hass, allow_ips={ip_address}),
        local_addr=(_IP_WILDCARD, SIP_PORT),
    )
    hass.data[DOMAIN] = transport

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload VoIP."""
    transport = hass.data.pop(DOMAIN, None)
    if transport is not None:
        transport.close()
        _LOGGER.debug("Shut down VoIP server")

    return True
