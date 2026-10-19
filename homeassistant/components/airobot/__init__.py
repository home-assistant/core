"""The Airobot integration."""

from modbus_connection import ModbusTcpParams
from pyairobotmodbus import DEFAULT_PORT, DEFAULT_UNIT_ID

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_VENTILATION, DOMAIN
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


async def async_setup_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
    """Set up Airobot from a config entry."""
    coordinator: AirobotDataUpdateCoordinator | AirobotVUCoordinator
    if _is_ventilation_entry(entry):
        try:
            unit = async_get_unit(
                hass,
                entry,
                ModbusTcpParams(host=entry.data[CONF_HOST], port=DEFAULT_PORT),
                DEFAULT_UNIT_ID,
            )
        # Another integration holds the unit over different link settings
        except HomeAssistantError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="modbus_link_conflict",
                translation_placeholders={"host": entry.data[CONF_HOST]},
            ) from err
        coordinator = AirobotVUCoordinator(hass, entry, unit)
        platforms = VU_PLATFORMS
    else:
        coordinator = AirobotDataUpdateCoordinator(hass, entry)
        platforms = THERMOSTAT_PLATFORMS

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_unload_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
    """Unload a config entry."""
    platforms = VU_PLATFORMS if _is_ventilation_entry(entry) else THERMOSTAT_PLATFORMS
    await hass.config_entries.async_unload_platforms_or_raise(entry, platforms)
