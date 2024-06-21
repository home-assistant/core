"""Sensor for Suez Water Consumption data."""

from __future__ import annotations

from datetime import timedelta
import logging

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_COUNTER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Suez Water sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SuezSensor(client, entry.data[CONF_COUNTER_ID])], True)


class SuezSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_usage_yesterday"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_device_class = SensorDeviceClass.WATER

    def __init__(self, client: SuezClient, counter_id: int) -> None:
        """Initialize the data object."""
        self.client = client
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{counter_id}_water_usage_yesterday"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(counter_id))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Suez",
        )

    def _fetch_data(self) -> None:
        """Fetch latest data from Suez."""
        try:
            self.client.update()
            # _state holds the volume of consumed water during previous day
            self._attr_native_value = self.client.state
            self._attr_available = True
            self._attr_attribution = self.client.attributes["attribution"]

            self._attr_extra_state_attributes["this_month_consumption"] = {}
            for item in self.client.attributes["thisMonthConsumption"]:
                self._attr_extra_state_attributes["this_month_consumption"][item] = (
                    self.client.attributes["thisMonthConsumption"][item]
                )
            self._attr_extra_state_attributes["previous_month_consumption"] = {}
            for item in self.client.attributes["previousMonthConsumption"]:
                self._attr_extra_state_attributes["previous_month_consumption"][
                    item
                ] = self.client.attributes["previousMonthConsumption"][item]
            self._attr_extra_state_attributes["highest_monthly_consumption"] = (
                self.client.attributes["highestMonthlyConsumption"]
            )
            self._attr_extra_state_attributes["last_year_overall"] = (
                self.client.attributes["lastYearOverAll"]
            )
            self._attr_extra_state_attributes["this_year_overall"] = (
                self.client.attributes["thisYearOverAll"]
            )
            self._attr_extra_state_attributes["history"] = {}
            for item in self.client.attributes["history"]:
                self._attr_extra_state_attributes["history"][item] = (
                    self.client.attributes["history"][item]
                )

        except PySuezError:
            self._attr_available = False
            _LOGGER.warning("Unable to fetch data")

    def update(self) -> None:
        """Return the latest collected data from Suez."""
        self._fetch_data()
        _LOGGER.debug("Suez data state is: %s", self.native_value)
