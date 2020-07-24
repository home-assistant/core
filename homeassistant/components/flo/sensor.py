"""Support for Flo Water Monitor sensors."""
from datetime import datetime, timedelta
import logging

from homeassistant.const import VOLUME_GALLONS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN as FLO_DOMAIN

DEPENDENCIES = ["flo"]

WATER_ICON = "mdi:water"
MIN_TIME_BETWEEN_USAGE_UPDATES = timedelta(seconds=60)

NAME_DAILY_USAGE = "Daily Water"
NAME_MONTHLY_USAGE = "Monthly Water"
NAME_YEARLY_USAGE = "Yearly Water"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    client = hass.data[FLO_DOMAIN][config_entry.entry_id]["client"]
    locations = hass.data[FLO_DOMAIN]["locations"]

    async_add_entities(
        [
            FloDailyUsageSensor(FloUsageData(location["id"], client))
            for location in locations
        ],
        True,
    )


class FloUsageData:
    """Track and query usage data."""

    def __init__(self, location_id, client):
        """Initialize the usage data."""
        self._location_id = location_id
        self._client = client
        self._water_usage = None

    @Throttle(MIN_TIME_BETWEEN_USAGE_UPDATES)
    async def async_update(self):
        """Query and store usage data."""
        today = datetime.today()
        start_date = datetime(today.year, today.month, today.day, 0, 0)
        end_date = datetime(today.year, today.month, today.day, 23, 59, 59, 999000)
        self._water_usage = await self._client.water.get_consumption_info(
            self._location_id, start_date, end_date
        )
        _LOGGER.debug("Updated Flo consumption data: %s", self._water_usage)

    def usage(self):
        """Return the day's usage."""
        if not self._water_usage:
            return None
        return self._water_usage["aggregations"]["sumTotalGallonsConsumed"]


class FloDailyUsageSensor(Entity):
    """Monitors the daily water usage."""

    def __init__(self, flo_usage_data):
        """Initialize the daily water usage sensor."""
        self._flo_usage_data = flo_usage_data
        self._state = None

    @property
    def name(self):
        """Return the name for daily usage."""
        return NAME_DAILY_USAGE

    @property
    def icon(self):
        """Return the daily usage icon."""
        return WATER_ICON

    @property
    def state(self):
        """Return the current daily usage."""
        return round(self._flo_usage_data.usage(), 1)

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def unit_of_measurement(self):
        """Return gallons as the unit measurement for water."""
        return VOLUME_GALLONS

    async def async_update(self):
        """Retrieve the latest daily usage."""
        await self._flo_usage_data.async_update()
