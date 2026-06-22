"""The Voice over IP integration."""

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

from .const import CONF_SIP_PORT, DOMAIN
from .devices import VoIPDevices
from .store import VoipStore
from .voip import HassVoipDatagramProtocol

PLATFORMS = (
    Platform.ASSIST_SATELLITE,
    Platform.SELECT,
    Platform.SWITCH,
)
_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"

__all__ = [
    "DOMAIN",
    "async_remove_config_entry_device",
    "async_setup_entry",
    "async_unload_entry",
]


@dataclass
class DomainData:
    """Domain data."""

    transport: asyncio.DatagramTransport
    protocol: HassVoipDatagramProtocol
    devices: VoIPDevices


@dataclass
class VoipData:
    """Voip Runtime Data."""

    store: VoipStore
    domain_data: DomainData


type VoipConfigEntry = ConfigEntry[VoipData]


async def async_setup_entry(hass: HomeAssistant, entry: VoipConfigEntry) -> bool:
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

    sip_port = entry.options.get(CONF_SIP_PORT, SIP_PORT)
    store = VoipStore(hass, entry.entry_id)
    devices = VoIPDevices(hass, entry, store)
    await devices.async_setup()
    transport, protocol = await _create_sip_server(
        hass,
        lambda: HassVoipDatagramProtocol(hass, devices),
        sip_port,
    )
    _LOGGER.debug("Listening for VoIP calls on port %s", sip_port)
    entry.runtime_data = VoipData(store, DomainData(transport, protocol, devices))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _create_sip_server(
    hass: HomeAssistant,
    protocol_factory: Callable[
        [],
        asyncio.DatagramProtocol,
    ],
    sip_port: int,
) -> tuple[asyncio.DatagramTransport, HassVoipDatagramProtocol]:
    transport, protocol = await hass.loop.create_datagram_endpoint(
        protocol_factory,
        local_addr=(_IP_WILDCARD, sip_port),
    )

    if not isinstance(protocol, HassVoipDatagramProtocol):
        raise TypeError(f"Expected HassVoipDatagramProtocol, got {protocol}")

    return transport, protocol


async def async_unload_entry(hass: HomeAssistant, entry: VoipConfigEntry) -> bool:
    """Unload VoIP."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.debug("Shutting down VoIP server")
        entry.runtime_data.domain_data.transport.close()
        await entry.runtime_data.domain_data.protocol.wait_closed()
        _LOGGER.debug("VoIP server shut down successfully")

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove device from a config entry."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: VoipConfigEntry) -> None:
    """Remove VoIP entry."""
    if "user" in entry.data and (
        user := await hass.auth.async_get_user(entry.data["user"])
    ):
        await hass.auth.async_remove_user(user)

    await entry.runtime_data.store.async_remove()
