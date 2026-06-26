"""The HiFiBerry integration."""

from dataclasses import dataclass

from aiohifiberry import AudioControlClient, AudioControlError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT

PLATFORMS = [Platform.MEDIA_PLAYER]


@dataclass
class HiFiBerryData:
    """HiFiBerry runtime data."""

    client: AudioControlClient


type HiFiBerryConfigEntry = ConfigEntry[HiFiBerryData]


async def async_migrate_entry(hass: HomeAssistant, entry: HiFiBerryConfigEntry) -> bool:
    """Migrate legacy HiFiBerry OS config entries to HBOS NG settings."""
    if entry.version >= 2:
        return True

    data = dict(entry.data)
    data.pop("authtoken", None)
    if data.get(CONF_PORT) in (None, 81):
        data[CONF_PORT] = DEFAULT_PORT

    hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HiFiBerryConfigEntry) -> bool:
    """Set up HiFiBerry from a config entry."""
    client = AudioControlClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

    try:
        await client.async_update()
    except AudioControlError as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = HiFiBerryData(client=client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HiFiBerryConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
