"""Kermi heatpump integration for Home Assistant."""

from datetime import timedelta
from functools import partial
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MODBUS_REGISTERS

# Create a logger
logger = logging.getLogger(__name__)

PLATFORMS = ["water_heater"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up kermi from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create a ModbusTcpClient
    client = AsyncModbusTcpClient(
        host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]
    )

    # Connect to the client
    try:
        await client.connect()
    except ConnectionException as err:
        raise ConfigEntryNotReady from err

    coordinator = DataUpdateCoordinator(
        hass,
        logger,
        name="kermi",
        update_method=partial(
            async_update_data, client, entry.data["water_heater_device_address"]
        ),
        update_interval=timedelta(minutes=1),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }
    # Forward the setup to the water heater platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "water_heater")
    )

    try:
        # Fetch initial data
        await coordinator.async_config_entry_first_refresh()
    except ModbusIOException as e:
        logger.error("Modbus IO exception: %s", e)
        return False

    if not coordinator.data:
        return False

    return True


async def async_update_data(client, device_address):
    """Fetch data from Kermi's IFM via modbus TCP."""
    data = {}
    for device, registers in MODBUS_REGISTERS.items():
        sorted_registers = sorted(registers.items(), key=lambda x: x[1]["register"])
        bulk_read = []
        for i, sorted_register in enumerate(sorted_registers):
            if (
                i < len(sorted_registers) - 1
                and sorted_registers[i + 1][1]["register"]
                - sorted_register[1]["register"]
                == 1
            ):
                bulk_read.append(sorted_register)
            else:
                bulk_read.append(sorted_register)
                min_address = bulk_read[0][1]["register"]
                count = bulk_read[-1][1]["register"] - min_address + 1
                try:
                    result = await client.read_input_registers(
                        min_address, count, device_address
                    )
                    for register_name, register_info in bulk_read:
                        register_address = register_info["register"]
                        if register_info["data_type"] == "int16":
                            data[f"{device}_{register_name}"] = result.registers[
                                register_address - min_address
                            ] * register_info.get("scale_factor", 1)
                        elif register_info["data_type"] == "enum":
                            data[f"{device}_{register_name}"] = register_info[
                                "mapping"
                            ].get(
                                result.registers[register_address - min_address],
                                "unknown",
                            )
                except Exception as err:
                    raise UpdateFailed(f"Error fetching data: {err}") from err
                bulk_read = []
    logger.debug("new data fetched via modbus: %s", data)
    return data
