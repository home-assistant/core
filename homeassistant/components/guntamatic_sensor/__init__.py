"""The guntamatic integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from guntamatic.heater import Heater

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

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

    host = entry.data[CONF_HOST]
    heater = Heater(host)

    # initial connectivity check
    initial_data = None
    try:
        initial_data = await hass.async_add_executor_job(heater.get_data)
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Guntamatic heater: {err}"
        ) from err

    if not initial_data:
        raise ConfigEntryNotReady("Cannot connect to Guntamatic heater")

    async def async_update_data() -> dict[str, list[str]]:
        """Fetch all sensor data from the heater.

        Expected return format:
            {
                "Boiler Temperature": [68.5, "°C"],
                "Flue Temperature": [115.2, "°C"],
                "Power Output": [12.4, "kW"],
            }
        """

        data: dict[str, list[str]] = await hass.async_add_executor_job(heater.get_data)
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

    coordinator.data = initial_data
    entry.runtime_data = GuntamaticData(heater=heater, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: GuntamaticConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1]
        == config_entry.runtime_data.coordinator.data.get("Serial", [None])[0]
    )
