"""The Kii Audio integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SYSTEM_ID
from .coordinator import KiiAudioCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

type KiiAudioConfigEntry = ConfigEntry[KiiAudioCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KiiAudioConfigEntry) -> bool:
    """Set up Kii Audio from a config entry."""
    coordinator = KiiAudioCoordinator(hass, entry)
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
    if isinstance(system_name, str) and system_name and entry.title != system_name:
        hass.config_entries.async_update_entry(entry, title=system_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KiiAudioConfigEntry) -> bool:
    """Unload a Kii Audio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.stop()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: KiiAudioConfigEntry) -> bool:
    """Migrate old config entries."""
    data = dict(entry.data)
    data.pop(CONF_PORT, None)
    system_id = data.get(CONF_SYSTEM_ID)

    if data != entry.data or (entry.unique_id is None and isinstance(system_id, str)):
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=system_id if isinstance(system_id, str) else entry.unique_id,
        )

    return True
