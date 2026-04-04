"""The guntamatic integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from guntamatic.heater import Heater

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL

# For your initial PR, limit it to 1 platform.
_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR]

type GuntamaticConfigEntry = ConfigEntry[Heater]


@dataclass
class GuntamaticData:
    """Data for the Guntamatic integration."""

    heater: Heater
    coordinator: DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Set up guntamatic from a config entry."""

    host = entry.data["host"]
    heater = Heater(host)
    if not await hass.async_add_executor_job(heater.get_data):
        raise ConfigEntryNotReady("Cannot connect to Guntamatic heater")

    async def async_update_data():
        """Fetch all sensor data from the heater.

        Expected return format:
            {
                "Boiler Temperature": [68.5, "°C"],
                "Flue Temperature": [115.2, "°C"],
                "Power Output": [12.4, "kW"],
            }
        """

        data = await hass.async_add_executor_job(heater.get_data)
        if not data:
            raise UpdateFailed("No data received from heater")
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name="guntamatic_sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        config_entry=entry,
    )

    try:
        # Fetch initial data
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Error while connecting to {host}: {err}") from err

    entry.runtime_data = GuntamaticData(heater=heater, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
