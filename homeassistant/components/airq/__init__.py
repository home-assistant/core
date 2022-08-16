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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up air-Q from a config entry."""
    # entry.data is a dict with the data from STEP_USER_SCHEMA:
    # entry.data.keys: [CONF_IP_ADDRESS, CONF_PASSWORD]

    # Set up the "access point"
    airq = AirQ(entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD])

    # target_route: Final = {True: "average", False: "data"}[entry.data[CONF_SHOW_AVG]]
    # scan_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
    target_route = "average"
    scan_interval = timedelta(seconds=10)

    # TODO: consider adding a more specific type alias, e.g.
    # Data = int | float | list[float] | str | dict[str, str]
    async def update_callback() -> dict:
        """Fetch the data from the device.

        Function is meant as an async closure, or partial(airq.get, target_route)
        Additionally, the result dictionary is stripped of the errors. Subject to
        a discussion
        """
        data = await airq.get(target_route)
        return airq.drop_errors_from_data(data)

    # Coordinator is responsible for querying the device through the callback.
    # The result of the callback is stored in coordinator.data dictionary
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=update_callback,
        update_interval=scan_interval,
    )
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
