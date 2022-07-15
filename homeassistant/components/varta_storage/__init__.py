"""The VARTA Storage integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import async_timeout
from vartastorage import vartastorage

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TIME_HOURS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VARTA Storage from a config entry."""
    varta = vartastorage.VartaStorage(entry.data["host"], entry.data["port"])
    try:
        varta.client.connect()
    except Exception as ex:
        _LOGGER.warning("Could not connect to modbus server")
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)

    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener

    async def async_update_data():
        """Fetch data and preo-process the data from API endpoint."""

        def sync_update():
            """Utilizing synchronous task as the used PyPI Package is not built with async."""
            varta = vartastorage.VartaStorage(entry.data["host"], entry.data["port"])
            # Collect all data from the device at once
            varta.get_all_data()
            return varta

        try:
            async with async_timeout.timeout(10):

                # Call synchronous task to update the sensor values
                result = await hass.async_add_executor_job(sync_update)
        except Exception as failed_update:
            raise UpdateFailed("Error communicating with API") from failed_update

        thisdict = {}
        thisdict[0] = {
            "name": "VARTA state of charge",
            "native_value": result.soc,
            "device_class": "battery",
            "state_class": "measurement",
            "native_unit_of_measurement": PERCENTAGE,
        }
        thisdict[1] = {
            "name": "VARTA grid power",
            "native_value": result.grid_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[2] = {
            "name": "VARTA to_grid power",
            "native_value": result.to_grid_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[3] = {
            "name": "VARTA from_grid power",
            "native_value": result.from_grid_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[4] = {
            "name": "VARTA state",
            "native_value": result.state,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }
        thisdict[5] = {
            "name": "VARTA state text",
            "native_value": result.state_text,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }
        thisdict[6] = {
            "name": "VARTA active power",
            "native_value": result.active_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[7] = {
            "name": "VARTA apparent power",
            "native_value": result.apparent_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[8] = {
            "name": "VARTA charge power",
            "native_value": result.charge_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[9] = {
            "name": "VARTA discharge power",
            "native_value": result.discharge_power,
            "device_class": "power",
            "state_class": "measurement",
            "native_unit_of_measurement": POWER_WATT,
        }
        thisdict[10] = {
            "name": "VARTA error code",
            "native_value": result.error_code,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }
        thisdict[11] = {
            "name": "VARTA total charged energy",
            "native_value": result.total_charged_energy,
            "device_class": "energy",
            "state_class": "total",
            "native_unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        }
        thisdict[12] = {
            "name": "VARTA total grid to home",
            "native_value": result.grid_to_home,
            "device_class": "energy",
            "state_class": "total",
            "native_unit_of_measurement": ENERGY_WATT_HOUR,
        }
        thisdict[13] = {
            "name": "VARTA total home to grid",
            "native_value": result.home_to_grid,
            "device_class": "energy",
            "state_class": "total",
            "native_unit_of_measurement": ENERGY_WATT_HOUR,
        }
        thisdict[14] = {
            "name": "VARTA invertert total charged",
            "native_value": result.inverter_total_charged,
            "device_class": "energy",
            "state_class": "total",
            "native_unit_of_measurement": ENERGY_WATT_HOUR,
        }
        thisdict[15] = {
            "name": "VARTA invertert total discharged",
            "native_value": result.inverter_total_discharged,
            "device_class": "energy",
            "state_class": "total",
            "native_unit_of_measurement": ENERGY_WATT_HOUR,
        }
        thisdict[16] = {
            "name": "VARTA charge cycle counter",
            "native_value": result.charge_cycle_counter,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }
        thisdict[17] = {
            "name": "VARTA hours until filter maintenance",
            "native_value": result.hours_until_filter_maintenance,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": TIME_HOURS,
        }
        thisdict[18] = {
            "name": "VARTA fan",
            "native_value": result.fan,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }
        thisdict[19] = {
            "name": "VARTA main",
            "native_value": result.main,
            "device_class": "None",
            "state_class": "None",
            "native_unit_of_measurement": None,
        }

        return thisdict

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=1),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, "sensor")]
        )
    )

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
