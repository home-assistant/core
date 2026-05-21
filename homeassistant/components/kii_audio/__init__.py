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
    if (system_id := entry.data.get(CONF_SYSTEM_ID)) and entry.unique_id != system_id:
        if entry.unique_id is None:
            hass.config_entries.async_update_entry(entry, unique_id=system_id)
        else:
            await hass.config_entries.async_remove(entry.entry_id)
            return True

    if CONF_PORT in entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={key: val for key, val in entry.data.items() if key != CONF_PORT},
        )

    coordinator = KiiAudioCoordinator(hass, entry)
    await coordinator.async_start()
    try:
        await coordinator.async_wait_ready()
    except TimeoutError as err:
        await coordinator.async_stop()
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
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await coordinator.async_stop()
    return unload_ok
