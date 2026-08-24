"""Owns both coordinators; modbus hands out the unit, sofar-modbus reads."""

from datetime import timedelta
import logging

from modbus_connection import ModbusTcpParams
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_UNIT_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, SETTINGS_SCAN_INTERVAL
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData

_LOGGER = logging.getLogger(__name__)

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
        timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    settings = SofarDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    # Sequential: both share one device/unit, and a Modbus link answers
    # one request at a time - concurrent setups would race each other.
    await readings.async_config_entry_first_refresh()
    # No settings-backed platform exists yet, so a settings failure must
    # not block setup of the working reading-backed sensors.
    await settings.async_refresh()

    entry.runtime_data = SofarRuntimeData(readings, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
