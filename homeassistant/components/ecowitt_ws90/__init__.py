"""The Ecowitt WS90 integration."""

from ecowitt_ws90_modbus import WS90
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID
from .coordinator import WS90ConfigEntry, WS90DataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WS90ConfigEntry) -> bool:
    """Set up Ecowitt WS90 from a config entry."""
    # Shared with any other integration on this gateway, and closed when the
    # last entry holding a unit on it unloads. The WS90 only ever speaks RTU
    # framing, whether reached directly or (the common case) through an
    # RTU-over-TCP serial gateway.
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(
            host=entry.data[CONF_HOST], port=entry.data[CONF_PORT], framer="rtu"
        ),
        entry.data[CONF_UNIT_ID],
    )

    coordinator = WS90DataUpdateCoordinator(hass, entry, WS90(unit))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WS90ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
