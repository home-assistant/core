"""The Voice over IP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from voip_utils import SIP_PORT

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .devices import VoIPDevices
from .voip import HassVoipDatagramProtocol

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
)
_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
    "async_remove_config_entry_device",
]


@dataclass
class DomainData:
    """Domain data."""

    transport: asyncio.DatagramTransport
    devices: VoIPDevices


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VoIP integration from a config entry."""
    # Make sure there is a valid user ID for VoIP in the config entry
    if (
        "user" not in entry.data
        or (await hass.auth.async_get_user(entry.data["user"])) is None
    ):
        voip_user = await hass.auth.async_create_system_user(
            "Voice over IP", group_ids=[GROUP_ID_USER]
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "user": voip_user.id}
        )

    devices = VoIPDevices(hass, entry)
    devices.async_setup()
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
    """Remove device from a config entry."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove VoIP entry."""
    if "user" in entry.data and (
        user := await hass.auth.async_get_user(entry.data["user"])
    ):
        await hass.auth.async_remove_user(user)
