"""The Airobot integration."""

from typing import Any

from modbus_connection import ModbusTcpParams
from pyairobotmodbus import DEFAULT_PORT, DEFAULT_UNIT_ID

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_VENTILATION
from .coordinator import (
    AirobotConfigEntry,
    AirobotDataUpdateCoordinator,
    AirobotVUCoordinator,
)

THERMOSTAT_PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

VU_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


def _is_ventilation_entry(entry: AirobotConfigEntry) -> bool:
    """Return True if the config entry is for a ventilation unit."""
    return entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_VENTILATION


async def _async_migrate_vu_unique_ids(
    hass: HomeAssistant, entry: AirobotConfigEntry
) -> None:
    """Move entities created before the MAC was known to MAC unique IDs."""
    if (mac := entry.unique_id) is None:
        return
    prefix = f"{entry.entry_id}_"

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if not entity_entry.unique_id.startswith(prefix):
            return None
        return {"new_unique_id": f"{mac}_{entity_entry.unique_id.removeprefix(prefix)}"}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


async def async_setup_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> bool:
    """Set up Airobot from a config entry."""
    coordinator: AirobotDataUpdateCoordinator | AirobotVUCoordinator
    if _is_ventilation_entry(entry):
        unit = async_get_unit(
            hass,
            entry,
            ModbusTcpParams(host=entry.data[CONF_HOST], port=DEFAULT_PORT),
            DEFAULT_UNIT_ID,
        )
        coordinator = AirobotVUCoordinator(hass, entry, unit)
        await _async_migrate_vu_unique_ids(hass, entry)
        platforms = VU_PLATFORMS
    else:
        coordinator = AirobotDataUpdateCoordinator(hass, entry)
        platforms = THERMOSTAT_PLATFORMS

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = VU_PLATFORMS if _is_ventilation_entry(entry) else THERMOSTAT_PLATFORMS
    return await hass.config_entries.async_unload_platforms(entry, platforms)
