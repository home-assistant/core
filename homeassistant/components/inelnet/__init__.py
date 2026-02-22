"""INELNET Blinds integration. One device per channel; no multi-channel (group) control."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CHANNELS


@dataclass
class InelnetRuntimeData:
    """Runtime data for INELNET config entry."""

    host: str
    channels: list[int]


type InelnetConfigEntry = ConfigEntry[InelnetRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: InelnetConfigEntry) -> bool:
    """Set up INELNET: one device per channel, each entity controls a single channel only."""
    host = entry.data[CONF_HOST]
    channels = entry.data[CONF_CHANNELS]

    session = async_get_clientsession(hass)
    url = f"http://{host}/msg.htm"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status >= 400:
                raise ConfigEntryNotReady(
                    f"Controller at {host} returned {resp.status}"
                ) from None
    except (aiohttp.ClientError, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to controller at {host}") from err

    entry.runtime_data = InelnetRuntimeData(host=host, channels=channels)

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.COVER, Platform.BUTTON]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: InelnetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.COVER, Platform.BUTTON]
    )
