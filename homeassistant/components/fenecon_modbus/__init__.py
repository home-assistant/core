"""The Fenecon Modbus integration."""

from fenecon_modbus import FeneconModbusClient

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID
from .coordinator import FeneconConfigEntry, FeneconCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FeneconConfigEntry) -> None:
    """Set up Fenecon Modbus from a config entry."""
    client = FeneconModbusClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        unit_id=entry.data[CONF_UNIT_ID],
    )
    # Also runs when setup fails, so the socket never outlives the entry
    entry.async_on_unload(client.close)

    coordinator = FeneconCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: FeneconConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
