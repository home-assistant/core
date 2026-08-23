"""Owns the connection and both coordinators; sofar-modbus reads registers."""

from datetime import timedelta
import logging

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import (
    CONF_READ_EPS,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    serial = entry.unique_id
    assert serial is not None
    inverter_type, model = identify(serial)
    if not inverter_type:
        raise ConfigEntryError(f"Unrecognized Sofar inverter model for {entry.title}")

    connection = ModbusConnection(
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )
    )
    entry.async_on_unload(connection.close)

    device = SofarInverter(
        connection.for_unit(entry.data[CONF_UNIT_ID]),
        serial_number=serial,
        model=model,
        inverter_type=inverter_type,
        read_eps=entry.data.get(CONF_READ_EPS, False),
    )

    readings = SofarDataUpdateCoordinator(
        hass,
        entry,
        connection,
        device,
        device.async_update_readings,
        timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        recycle_stuck_link=True,
    )
    settings = SofarDataUpdateCoordinator(
        hass,
        entry,
        connection,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    # Sequential: both share one device/connection, and a Modbus link
    # answers one request at a time — concurrent setups would race.
    await readings.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()

    entry.runtime_data = SofarRuntimeData(readings, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
