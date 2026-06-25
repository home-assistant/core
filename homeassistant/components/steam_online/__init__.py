"""The Steam integration."""

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SteamConfigEntry
) -> bool:
    """Migrate old entry."""

    if config_entry.version < 2:
        # Migrate entity unique id

        if TYPE_CHECKING:
            assert config_entry.unique_id

        ent_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            ent_reg, config_entry.entry_id
        ):
            if not entity_entry.unique_id.startswith("sensor.steam_"):
                continue

            ent_reg.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=(
                    entity_entry.unique_id.removeprefix("sensor.steam_") + "_account"
                ),
            )

        hass.config_entries.async_update_entry(config_entry, version=2)

    return True
