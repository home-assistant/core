"""Sensor for Suez Water Consumption data."""
from __future__ import annotations

from datetime import timedelta
import logging

from pysuez import SuezClient
from pysuez.client import PySuezError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfVolume
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)

CONF_COUNTER_ID = "counter_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_COUNTER_ID): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    counter_id = config[CONF_COUNTER_ID]
    try:
        client = SuezClient(username, password, counter_id)

        if not client.check_credentials():
            _LOGGER.warning("Wrong username and/or password")
            return

    except PySuezError:
        _LOGGER.warning("Unable to create Suez Client")
        return

    add_entities([SuezSensor(client)], True)


class SuezSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Suez Water Client"
    _attr_icon = "mdi:water-pump"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_device_class = SensorDeviceClass.WATER

    def __init__(self, client: SuezClient) -> None:
        """Initialize the data object."""
        self.client = client
        self._attr_extra_state_attributes = {}

    def _fetch_data(self):
        """Fetch latest data from Suez."""
        try:
            self.client.update()
            # _state holds the volume of consumed water during previous day
            self._attr_native_value = self.client.state
            self._attr_available = True
            self._attr_attribution = self.client.attributes["attribution"]

            self._attr_extra_state_attributes["this_month_consumption"] = {}
            for item in self.client.attributes["thisMonthConsumption"]:
                self._attr_extra_state_attributes["this_month_consumption"][
                    item
                ] = self.client.attributes["thisMonthConsumption"][item]
            self._attr_extra_state_attributes["previous_month_consumption"] = {}
            for item in self.client.attributes["previousMonthConsumption"]:
                self._attr_extra_state_attributes["previous_month_consumption"][
                    item
                ] = self.client.attributes["previousMonthConsumption"][item]
            self._attr_extra_state_attributes[
                "highest_monthly_consumption"
            ] = self.client.attributes["highestMonthlyConsumption"]
            self._attr_extra_state_attributes[
                "last_year_overall"
            ] = self.client.attributes["lastYearOverAll"]
            self._attr_extra_state_attributes[
                "this_year_overall"
            ] = self.client.attributes["thisYearOverAll"]
            self._attr_extra_state_attributes["history"] = {}
            for item in self.client.attributes["history"]:
                self._attr_extra_state_attributes["history"][
                    item
                ] = self.client.attributes["history"][item]

        except PySuezError:
            self._attr_available = False
            _LOGGER.warning("Unable to fetch data")

    def update(self) -> None:
        """Return the latest collected data from Suez."""
        self._fetch_data()
        _LOGGER.debug("Suez data state is: %s", self.native_value)
