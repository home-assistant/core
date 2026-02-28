"""INELNET Blinds integration. One device per channel; no multi-channel (group) control."""

from __future__ import annotations

from dataclasses import dataclass

from inelnet_api import InelnetChannel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CHANNELS


@dataclass
class InelnetRuntimeData:
    """Runtime data for INELNET config entry. One client per channel."""

    host: str
    channels: list[int]
    clients: dict[int, InelnetChannel]


type InelnetConfigEntry = ConfigEntry[InelnetRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: InelnetConfigEntry) -> bool:
    """Set up INELNET: one device per channel, each entity controls a single channel only."""
    host = entry.data[CONF_HOST]
    channels = entry.data[CONF_CHANNELS]
    if not channels:
        raise ConfigEntryError("No channels configured")

    clients = {ch: InelnetChannel(host, ch) for ch in channels}
    session = async_get_clientsession(hass)

    def _raise_not_ready(msg: str) -> None:
        raise ConfigEntryNotReady(msg) from None

    try:
        if not await clients[channels[0]].ping(session=session):
            _raise_not_ready(f"Controller at {host} did not respond or returned error")
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(f"Cannot connect to controller at {host}") from err

    entry.runtime_data = InelnetRuntimeData(
        host=host, channels=channels, clients=clients
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.COVER, Platform.BUTTON]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: InelnetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.COVER, Platform.BUTTON]
    )
