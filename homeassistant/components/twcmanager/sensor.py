"""Platform for sensor integration."""

from datetime import timedelta
import logging

from aiohttp.web import HTTPError
import async_timeout

from homeassistant.const import ELECTRICAL_CURRENT_AMPERE
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    # assuming API object stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await api.async_get_slave_twcs()
        except HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        ReportedAmpsActualSensor(coordinator, twc)
        for idx, twc in enumerate(coordinator.data)
    )


class ReportedAmpsActualSensor(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, twc):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.twc = twc
        self.entity_id = "sensor." + DOMAIN + "_" + self.twc + "_reported_amps_actual"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "TWC " + self.twc + " Reported Amps Actual"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.twc]["reportedAmpsActual"]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ELECTRICAL_CURRENT_AMPERE
