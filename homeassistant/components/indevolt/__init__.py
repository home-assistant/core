"""Home Assistant integration for indevolt device."""

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        # 1.1 -> 1.2: indevolt-api 1.8.3 changed IndevoltBattery.MAIN_HEATING_STATE
        # from 9079 to 9080, so migrate affected unique IDs.
        @callback
        def migrate_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, Any] | None:
            if entity_entry.unique_id.endswith("_9079"):
                return {
                    "new_unique_id": entity_entry.unique_id.removesuffix("_9079")
                    + "_9080"
                }
            return None

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(entry, version=1, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    coordinator = IndevoltCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up indevolt services (actions)."""

    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry.

    Clean up resources when integration is removed or reloaded.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
