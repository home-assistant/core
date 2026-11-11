"""The HP Printer integration."""

from homeassistant.const import CONF_SSL, Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER
from .coordinator import HpPrinterConfigEntry, HpPrinterDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HpPrinterConfigEntry) -> None:
    """Set up HP Printer from a config entry."""
    coordinator = HpPrinterDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HpPrinterConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: HpPrinterConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.minor_version < 2:
        LOGGER.debug("Migrating config entry from version 1.%s", entry.minor_version)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SSL: False}, minor_version=2
        )
