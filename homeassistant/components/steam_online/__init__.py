"""The Steam integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .coordinator import SteamConfigEntry, SteamDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Set up Steam from a config entry."""
    coordinator = SteamDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version < 2:
        # Migrate entity unique id

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            if entity_entry.unique_id.startswith("sensor.steam_"):
                new = entity_entry.unique_id.removeprefix("sensor.steam_") + "_account"
                return {"new_unique_id": new}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(entry, version=2)

    return True
