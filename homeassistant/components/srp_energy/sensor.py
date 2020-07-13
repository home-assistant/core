from datetime import datetime, timedelta
import logging
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

import async_timeout

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers import entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, DEFAULT_NAME, ENERGY_KWH, ICON, ATTRIBUTION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.

            start_date = datetime.now() + timedelta(days=-1)
            end_date = datetime.now()
            usage = api.usage(start_date, end_date)
            daily_usage = 0.0
            for _, _, _, kwh, _ in usage:
                daily_usage += float(kwh)
            return daily_usage
        except (ConnectError, HTTPError, Timeout, ValueError, TypeError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(minutes=5),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities([SrpEntity(coordinator)])


class SrpEntity(entity.Entity):
    def __init__(self, coordinator):
        self._name = "Usage"
        self.type = "usage"
        self.coordinator = coordinator
        self._unit_of_measurement = ENERGY_KWH
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
        return self._state

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
        """Return entity state.

      Example to show how we fetch data from coordinator.
      """
        return self.coordinator.data

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_state_attributes(self):
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
