"""The Flexit component, for AC units with a CI66 Modbus adapter."""

from homeassistant.const import CONF_SLAVE, Platform
from homeassistant.core import HomeAssistant

from .connection import create_modbus_connection
from .coordinator import FlexitConfigEntry, FlexitDataCoordinator

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Set up Flexit from a config entry."""
    connection = create_modbus_connection(entry.data)
    entry.async_on_unload(connection.close)

    coordinator = FlexitDataCoordinator(hass, entry, connection, entry.data[CONF_SLAVE])

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: FlexitConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
