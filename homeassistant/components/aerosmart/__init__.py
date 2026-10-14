"""The aerosmart integration."""

from aerosmart_modbus import AerosmartDevice
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import (
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DEFAULT_PORT,
    DOMAIN,
    LEGACY_CONF_CONNECTION,
    READINGS_SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import (
    AerosmartConfigEntry,
    AerosmartCoordinator,
    AerosmartRuntimeData,
)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def _async_initial_refresh(runtime: AerosmartRuntimeData) -> None:
    """Populate entities without blocking Home Assistant startup."""
    await runtime.readings.async_refresh()
    await runtime.settings.async_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: AerosmartConfigEntry) -> bool:
    """Set up aerosmart from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    runtime.initial_refresh_task = entry.async_create_background_task(
        hass,
        _async_initial_refresh(runtime),
        f"{entry.domain} initial refresh",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AerosmartConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: AerosmartConfigEntry) -> bool:
    """Migrate entries that referenced the withdrawn shared-connection integration."""
    if entry.version != 1 or LEGACY_CONF_CONNECTION not in entry.data:
        return True

    legacy_entry = hass.config_entries.async_get_entry(
        entry.data[LEGACY_CONF_CONNECTION]
    )
    if legacy_entry is None or CONF_HOST not in legacy_entry.data:
        return False

    host = str(legacy_entry.data[CONF_HOST]).strip().lower()
    port = int(legacy_entry.data.get(CONF_PORT, DEFAULT_PORT))
    data = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_UNIT_VENTILATION: int(entry.data[CONF_UNIT_VENTILATION]),
        CONF_UNIT_HEAT_PUMP: int(entry.data[CONF_UNIT_HEAT_PUMP]),
    }
    hass.config_entries.async_update_entry(
        entry,
        data=data,
        unique_id=f"{host}:{port}_{data[CONF_UNIT_VENTILATION]}_{data[CONF_UNIT_HEAT_PUMP]}",
        version=2,
    )
    return True
