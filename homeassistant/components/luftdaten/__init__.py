"""Support for Sensor.Community stations.

Sensor.Community was previously called Luftdaten, hence the domain differs from
the integration name.
"""

from __future__ import annotations

import logging
from typing import Any

from luftdaten import Luftdaten
from luftdaten.exceptions import LuftdatenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SENSOR_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensor.Community as config entry."""

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=str(entry.data[CONF_SENSOR_ID])
        )

    sensor_community = Luftdaten(entry.data[CONF_SENSOR_ID])

    async def async_update() -> dict[str, float | int]:
        """Update sensor/binary sensor data."""
        try:
            await sensor_community.get_data()
        except LuftdatenError as err:
            raise UpdateFailed("Unable to retrieve data from Sensor.Community") from err

        if not sensor_community.values:
            raise UpdateFailed("Did not receive sensor data from Sensor.Community")

        data: dict[str, float | int] = sensor_community.values
        data.update(sensor_community.meta)
        return data

    coordinator: DataUpdateCoordinator[dict[str, Any]] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{sensor_community.sensor_id}",
        update_interval=DEFAULT_SCAN_INTERVAL,
        update_method=async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Sensor.Community config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
