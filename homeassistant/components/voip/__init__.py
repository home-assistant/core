"""The Voice over IP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from voip_utils import SIP_PORT

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .devices import VoIPDevices
from .voip import HassVoipDatagramProtocol

PLATFORMS = (Platform.SWITCH,)
_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]


@dataclass
class DomainData:
    """Domain data."""

    transport: asyncio.DatagramTransport
    devices: VoIPDevices


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VoIP integration from a config entry."""
    devices = VoIPDevices(hass, entry)
    transport = await _create_sip_server(
        hass,
        lambda: HassVoipDatagramProtocol(hass, devices),
    )
    _LOGGER.debug("Listening for VoIP calls on port %s", SIP_PORT)

    hass.data[DOMAIN] = DomainData(transport, devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.debug("Shut down VoIP server")
        hass.data.pop(DOMAIN).transport.close()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove config entry from a device."""
    return True
