"""Support for SRP Energy Sensor."""
from datetime import datetime, timedelta
import logging

import async_timeout
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    ICON,
    MIN_TIME_BETWEEN_UPDATES,
    SENSOR_NAME,
    SENSOR_TYPE,
    SRP_ENERGY_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SRP Energy Usage sensor."""
    # API object stored here by __init__.py
    is_time_of_use = False
    api = hass.data[SRP_ENERGY_DOMAIN]
    if entry and entry.data:
        is_time_of_use = entry.data["is_tou"]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Fetch srp_energy data
            start_date = datetime.now() + timedelta(days=-1)
            end_date = datetime.now()
            with async_timeout.timeout(10):
                hourly_usage = await hass.async_add_executor_job(
                    api.usage,
                    start_date,
                    end_date,
                    is_time_of_use,
                )

                previous_daily_usage = 0.0
                for _, _, _, kwh, _ in hourly_usage:
                    previous_daily_usage += float(kwh)
                return previous_daily_usage
        except (TimeoutError) as timeout_err:
            raise UpdateFailed("Timeout communicating with API") from timeout_err
        except (ConnectError, HTTPError, Timeout, ValueError, TypeError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities([SrpEntity(coordinator)])


class SrpEntity(SensorEntity):
    """Implementation of a Srp Energy Usage sensor."""

    def __init__(self, coordinator):
        """Initialize the SrpEntity class."""
        self._name = SENSOR_NAME
        self.type = SENSOR_TYPE
        self.coordinator = coordinator
        self._unit_of_measurement = ENERGY_KILO_WATT_HOUR
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME} {self._name}"

    @property
    def unique_id(self):
        """Return sensor unique_id."""
        return self.type

    @property
    def state(self):
        """Return the state of the device."""
        if self._state:
            return f"{self._state:.2f}"
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def usage(self):
        """Return entity state."""
        if self.coordinator.data:
            return f"{self.coordinator.data:.2f}"
        return None

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data:
            return None
        attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

        return attributes

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        if self.coordinator.data:
            self._state = self.coordinator.data

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
