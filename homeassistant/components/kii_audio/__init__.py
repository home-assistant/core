"""The Kii Audio integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import KiiAudioCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

type KiiAudioConfigEntry = ConfigEntry[KiiAudioCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KiiAudioConfigEntry) -> bool:
    """Set up Kii Audio from a config entry."""
    coordinator = KiiAudioCoordinator(hass, entry, async_get_clientsession(hass))
    await coordinator.client.start()
    try:
        await coordinator.async_wait_ready()
    except TimeoutError as err:
        await coordinator.client.stop()
        raise ConfigEntryNotReady(
            "Timed out waiting for Kii Audio system info"
        ) from err

    entry.runtime_data = coordinator

    system_name = coordinator.data.get("systemName")
    if system_name and entry.title != system_name:
        hass.config_entries.async_update_entry(entry, title=system_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KiiAudioConfigEntry) -> bool:
    """Unload a Kii Audio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.stop()
    return unload_ok
