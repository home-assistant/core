"""The HiFiBerry integration."""

from aiohifiberry import AudioControlClient, AudioControlError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS = [Platform.MEDIA_PLAYER]


type HiFiBerryConfigEntry = ConfigEntry[AudioControlClient]


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

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HiFiBerryConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
