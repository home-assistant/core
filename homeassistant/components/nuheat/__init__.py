"""Support for NuHeat thermostats."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

import nuheat
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FLOOR_AREA,
    CONF_SERIAL_NUMBER,
    CONF_WATT_DENSITY,
    DEFAULT_WATT_DENSITY,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NuHeatEnergyData:
    """Energy data from NuHeat API."""

    energy_kwh: float | None
    heating_minutes: int


type NuHeatConfigEntry = ConfigEntry[
    tuple[Any, DataUpdateCoordinator, DataUpdateCoordinator[NuHeatEnergyData]]
]


def _get_thermostat(api, serial_number):
    """Authenticate and create the thermostat object."""
    api.authenticate()
    return api.get_thermostat(serial_number)


async def async_setup_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Set up NuHeat from a config entry."""
    conf = entry.data

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    serial_number = conf[CONF_SERIAL_NUMBER]

    api = nuheat.NuHeat(username, password)

    try:
        thermostat = await hass.async_add_executor_job(
            _get_thermostat, api, serial_number
        )
    except requests.exceptions.Timeout as ex:
        raise ConfigEntryNotReady from ex
    except requests.exceptions.HTTPError as ex:
        if (
            ex.response.status_code > HTTPStatus.BAD_REQUEST
            and ex.response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            _LOGGER.error("Failed to login to nuheat: %s", ex)
            return False
        raise ConfigEntryNotReady from ex
    except Exception as ex:  # noqa: BLE001
        _LOGGER.error("Failed to login to nuheat: %s", ex)
        return False

    async def _async_update_data():
        """Fetch data from API endpoint."""
        await hass.async_add_executor_job(thermostat.get_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"nuheat {serial_number}",
        update_method=_async_update_data,
        update_interval=timedelta(minutes=5),
    )

    # Energy coordinator
    async def _async_update_energy_data() -> NuHeatEnergyData:
        """Fetch energy data from NuHeat API."""
        try:
            energy = await hass.async_add_executor_job(thermostat.get_energy_usage)
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error fetching energy data: {err}") from err

        total_minutes = energy.heating_minutes
        api_kwh = energy.energy_kwh

        # Calculate energy from floor area and watt density if configured
        floor_area = entry.options.get(CONF_FLOOR_AREA)
        if floor_area:
            watt_density = entry.options.get(CONF_WATT_DENSITY, DEFAULT_WATT_DENSITY)
            # Power (watts) = floor_area (sqft) * watt_density (watts/sqft)
            # Energy (kWh) = power (watts) * time (minutes) / 60 / 1000
            power_watts = floor_area * watt_density
            calculated_kwh = (power_watts * total_minutes) / 60 / 1000
            energy_kwh: float | None = calculated_kwh
        elif api_kwh is not None:
            energy_kwh = api_kwh
        else:
            energy_kwh = None

        return NuHeatEnergyData(
            energy_kwh=energy_kwh,
            heating_minutes=total_minutes,
        )

    energy_coordinator: DataUpdateCoordinator[NuHeatEnergyData] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"nuheat energy {serial_number}",
        update_method=_async_update_energy_data,
        update_interval=timedelta(minutes=30),
    )

    # Initial refresh
    await coordinator.async_config_entry_first_refresh()
    await energy_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = (thermostat, coordinator, energy_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: NuHeatConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
