"""The air-Q integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioairq import AirQ

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_IP_ADDRESS, CONF_SECRET, CONF_TARGET_ROUTE, DOMAIN, TARGET_ROUTS

_LOGGER = logging.getLogger(__name__)

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up air-Q from a config entry."""

    # Set up the "access point"
    # TODO: add necessary fields to the config
    airq = AirQ(entry.data[CONF_IP_ADDRESS], entry.data[CONF_SECRET])

    # TODO: expose the configuration to retrieve the averages or the momentary data
    target_route = entry.data[CONF_TARGET_ROUTE]
    # Perhaps, this check should happen elsewhere
    assert (
        target_route in TARGET_ROUTS
    ), f"CONF_TARGET_ROUTE must be in {TARGET_ROUTS}, got {target_route}"

    # TODO: consider adding a more specific type alias, e.g.
    # Data = int | float | list[float] | str
    # I am mostly unsure of 'Status'. If its type can vary, may as well not bother here
    async def update_callback() -> dict:
        """Fetch desired route (data or average) from the device.

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
        update_interval=SCAN_INTERVAL,
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
