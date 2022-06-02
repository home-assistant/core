"""The radiotherm component data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import radiotherm
from radiotherm.thermostat import CommonThermostat

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class RadioThermData:
    """Data for the radiothem integration."""

    coordinator: DataUpdateCoordinator[RadioThermUpdate]
    tstat: CommonThermostat
    name: str
    hold_temp: int


@dataclass
class RadioThermUpdate:
    """An update from a radiotherm device."""

    tstat: dict[str, Any]
    humidity: int | None


def _get_name_from_host(host: str) -> str:
    return _get_name(radiotherm.get_thermostat(host))


async def async_get_name_from_host(hass: HomeAssistant, host: str) -> str:
    """Get the name of a thermostat."""
    return await hass.async_add_executor_job(_get_name_from_host, host)


def _get_device(host: str) -> CommonThermostat:
    return radiotherm.get_thermostat(host)


async def async_get_device(hass: HomeAssistant, host: str) -> None:
    """Get the thermostat object."""
    return await hass.async_add_executor_job(_get_device, host)


def _get_name(device: CommonThermostat) -> str:
    """Fetch the name from the thermostat."""
    return device.name["raw"]


async def async_get_name(hass: HomeAssistant, device: CommonThermostat) -> str:
    """Fetch the name from the thermostat."""
    return await hass.async_add_executor_job(_get_name, device)


def _get_data(device: CommonThermostat) -> RadioThermUpdate:
    # Request the current state from the thermostat.
    # Radio thermostats are very slow, and sometimes don't respond
    # very quickly.  So we need to keep the number of calls to them
    # to a bare minimum or we'll hit the Home Assistant 10 sec warning.  We
    # have to make one call to /tstat to get temps but we'll try and
    # keep the other calls to a minimum.  Even with this, these
    # thermostats tend to time out sometimes when they're actively
    # heating or cooling.
    tstat: dict[str, Any] = device.tstat["raw"]
    if isinstance(device, radiotherm.thermostat.CT80):
        humidity: int | None = device.humidity["raw"]
    else:
        humidity = None
    return RadioThermUpdate(tstat, humidity)


async def async_get_data(
    hass: HomeAssistant, device: CommonThermostat
) -> RadioThermUpdate:
    """Fetch the data from the thermostat."""
    return await hass.async_add_executor_job(_get_data, device)
