"""The KACO Modbus integration."""

from kaco_modbus import KacoInverter
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_UNIT_ID
from .coordinator import KacoConfigEntry, KacoDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: KacoConfigEntry) -> None:
    """Set up KACO Modbus from a config entry."""
    # Shared with any other integration on this gateway, and closed when the
    # last entry holding a unit on it unloads.
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )

    coordinator = KacoDataUpdateCoordinator(hass, entry, KacoInverter(unit))
    await coordinator.async_config_entry_first_refresh()

    # Registered up front, as the MPPT child devices need its registry id.
    inverter = dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id, device_info=coordinator.device_info
    )
    coordinator.inverter_device_id = inverter.id

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: KacoConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
