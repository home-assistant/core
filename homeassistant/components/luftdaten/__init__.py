"""Support for Luftdaten stations."""
from __future__ import annotations

import logging
from typing import Any

from luftdaten import Luftdaten
from luftdaten.exceptions import LuftdatenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SENSOR_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luftdaten as config entry."""

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_SENSOR_ID]
        )

    luftdaten = Luftdaten(entry.data[CONF_SENSOR_ID])

    async def async_update() -> dict[str, float | int]:
        """Update sensor/binary sensor data."""
        try:
            await luftdaten.get_data()
        except LuftdatenError as err:
            raise UpdateFailed("Unable to retrieve data from luftdaten.info") from err

        if not luftdaten.values:
            raise UpdateFailed("Did not receive sensor data from luftdaten.info")

        data: dict[str, float | int] = luftdaten.values
        data.update(luftdaten.meta)
        return data

    coordinator: DataUpdateCoordinator[dict[Any, Any]] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{luftdaten.sensor_id}",
        update_interval=DEFAULT_SCAN_INTERVAL,
        update_method=async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Luftdaten config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
