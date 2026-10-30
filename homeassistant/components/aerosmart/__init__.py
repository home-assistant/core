"""The aerosmart integration."""

from aerosmart_modbus import AerosmartDevice

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import (
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DOMAIN,
    READINGS_SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import (
    AerosmartConfigEntry,
    AerosmartCoordinator,
    AerosmartRuntimeData,
)
from .helpers import create_modbus_params

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: AerosmartConfigEntry) -> None:
    """Set up aerosmart from a config entry."""
    params = create_modbus_params(entry.data)
    try:
        unit_ventilation = async_get_unit(
            hass, entry, params, entry.data[CONF_UNIT_VENTILATION]
        )
        unit_heat_pump = async_get_unit(
            hass, entry, params, entry.data[CONF_UNIT_HEAT_PUMP]
        )
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="connect_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    device = AerosmartDevice(unit_ventilation, unit_heat_pump)
    readings = AerosmartCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        READINGS_SCAN_INTERVAL,
        "readings",
    )
    settings = AerosmartCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        SETTINGS_SCAN_INTERVAL,
        "settings",
    )
    runtime = AerosmartRuntimeData(device, readings, settings)
    entry.runtime_data = runtime
    await readings.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AerosmartConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
