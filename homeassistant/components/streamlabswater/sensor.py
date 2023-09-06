"""Support for Streamlabs Water Monitor Usage."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from . import DOMAIN as STREAMLABSWATER_DOMAIN

DEPENDENCIES = ["streamlabswater"]

WATER_ICON = "mdi:water"
MIN_TIME_BETWEEN_USAGE_UPDATES = timedelta(seconds=60)

NAME_DAILY_USAGE = "Daily Water"
NAME_MONTHLY_USAGE = "Monthly Water"
NAME_YEARLY_USAGE = "Yearly Water"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up water usage sensors."""
    client = hass.data[STREAMLABSWATER_DOMAIN]["client"]
    location_id = hass.data[STREAMLABSWATER_DOMAIN]["location_id"]
    location_name = hass.data[STREAMLABSWATER_DOMAIN]["location_name"]

    streamlabs_usage_data = StreamlabsUsageData(location_id, client)
    streamlabs_usage_data.update()

    add_devices(
        [
            StreamLabsDailyUsage(location_name, streamlabs_usage_data),
            StreamLabsMonthlyUsage(location_name, streamlabs_usage_data),
            StreamLabsYearlyUsage(location_name, streamlabs_usage_data),
        ]
    )


class StreamlabsUsageData:
    """Track and query usage data."""

    def __init__(self, location_id, client):
        """Initialize the usage data."""
        self._location_id = location_id
        self._client = client
        self._today = None
        self._this_month = None
        self._this_year = None

    @Throttle(MIN_TIME_BETWEEN_USAGE_UPDATES)
    def update(self):
        """Query and store usage data."""
        water_usage = self._client.get_water_usage_summary(self._location_id)
        self._today = round(water_usage["today"], 1)
        self._this_month = round(water_usage["thisMonth"], 1)
        self._this_year = round(water_usage["thisYear"], 1)

    def get_daily_usage(self):
        """Return the day's usage."""
        return self._today

    def get_monthly_usage(self):
        """Return the month's usage."""
        return self._this_month

    def get_yearly_usage(self):
        """Return the year's usage."""
        return self._this_year


class StreamLabsDailyUsage(SensorEntity):
    """Monitors the daily water usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS

    def __init__(self, location_name, streamlabs_usage_data):
        """Initialize the daily water usage device."""
        self._location_name = location_name
        self._streamlabs_usage_data = streamlabs_usage_data
        self._state = None

    @property
    def name(self) -> str:
        """Return the name for daily usage."""
        return f"{self._location_name} {NAME_DAILY_USAGE}"

    @property
    def native_value(self):
        """Return the current daily usage."""
        return self._streamlabs_usage_data.get_daily_usage()

    def update(self) -> None:
        """Retrieve the latest daily usage."""
        self._streamlabs_usage_data.update()


class StreamLabsMonthlyUsage(StreamLabsDailyUsage):
    """Monitors the monthly water usage."""

    @property
    def name(self) -> str:
        """Return the name for monthly usage."""
        return f"{self._location_name} {NAME_MONTHLY_USAGE}"

    @property
    def native_value(self):
        """Return the current monthly usage."""
        return self._streamlabs_usage_data.get_monthly_usage()


class StreamLabsYearlyUsage(StreamLabsDailyUsage):
    """Monitors the yearly water usage."""

    @property
    def name(self) -> str:
        """Return the name for yearly usage."""
        return f"{self._location_name} {NAME_YEARLY_USAGE}"

    @property
    def native_value(self):
        """Return the current yearly usage."""
        return self._streamlabs_usage_data.get_yearly_usage()
