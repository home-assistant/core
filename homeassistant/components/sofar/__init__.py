"""Integrate Sofar devices into Home Assistant."""

from datetime import timedelta

from modbus_connection import ModbusTcpParams
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_UNIT_ID, DOMAIN, SCAN_INTERVAL, SETTINGS_SCAN_INTERVAL
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    serial = entry.unique_id
    assert serial is not None
    inverter_type, model = identify(serial)
    if not inverter_type:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unrecognized_inverter_model",
            translation_placeholders={"title": entry.title},
        )

    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )

    device = SofarInverter(
        unit,
        serial_number=serial,
        model=model,
        inverter_type=inverter_type,
    )

    readings = SofarDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = SofarDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    await readings.async_config_entry_first_refresh()
    await settings.async_refresh()

    entry.runtime_data = SofarRuntimeData(readings, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
