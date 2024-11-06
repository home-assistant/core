"""Initialize the Acaia component."""

from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant

from .coordinator import AcaiaConfigEntry, AcaiaCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AcaiaConfigEntry) -> bool:
    """Set up Acaia as config entry."""

    coordinator = AcaiaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AcaiaConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: AcaiaConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version == 1:
        new = {**entry.data}
        new[CONF_MAC] = new["conf_mac_address"]

        entry.version = 2
        hass.config_entries.async_update_entry(entry, data=new)

    return True
