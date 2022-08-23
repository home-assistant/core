"""The air-Q integration.

This file defines the initialisation of the integration, invoked from ConfigFlow.
Integration setup defined here calls out to the platform setup (see sensors.py).
"""
from __future__ import annotations

from datetime import timedelta
import logging

from aioairq import AirQ

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, TARGET_ROUTE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class AirQCoordinator(DataUpdateCoordinator):
    """Coordinator is responsible for querying the device at a specified route."""

    config: dict = {}

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta,
        address: str,
        passw: str,
    ) -> None:
        """Initialise a custom coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.airq = AirQ(address, passw)

    async def _async_update_data(self) -> dict:
        """Fetch the data from the device.

        Function is meant as an async closure, or partial(airq.get, TARGET_ROUTE)
        Additionally, the result dictionary is stripped of the errors. Subject to
        a discussion
        """
        data = await self.airq.get(TARGET_ROUTE)
        return self.airq.drop_errors_from_data(data)

    async def async_fetch_config(self) -> None:
        """Fetch static config information from the device."""
        config = await self.airq.get("config")
        self.config = {
            "id": config["id"],
            "name": config["devicename"],
            "model": config["type"],
            "room_type": config["RoomType"].replace("-", " ").title(),
            "sw_version": config["air-Q-Software-Version"],
            "hw_version": config["air-Q-Hardware-Version"],
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up air-Q from a config entry."""

    # Set up the "access point"
    coordinator = AirQCoordinator(
        hass,
        update_interval=timedelta(seconds=10),
        address=entry.data[CONF_IP_ADDRESS],
        passw=entry.data[CONF_PASSWORD],
    )

    await coordinator.async_fetch_config()

    # Query the device for the first time and initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()

    # Record the coordinator in a global store
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
