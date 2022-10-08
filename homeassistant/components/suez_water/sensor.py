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
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, VOLUME_LITERS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)

CONF_COUNTER_ID = "counter_id"

NAME = "Suez Water Client"
ICON = "mdi:water-pump"

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

    _attr_name = NAME
    _attr_icon = ICON
    _attr_native_unit_of_measurement = VOLUME_LITERS
    _attr_device_class = SensorDeviceClass.VOLUME

    def __init__(self, client):
        """Initialize the data object."""
        self._attributes = {}
        self._state = None
        self._available = None
        self.client = client

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _fetch_data(self):
        """Fetch latest data from Suez."""
        try:
            self.client.update()
            # _state holds the volume of consumed water during previous day
            self._state = self.client.state
            self._available = True
            self._attributes["attribution"] = self.client.attributes["attribution"]
            self._attributes["this_month_consumption"] = {}
            for item in self.client.attributes["thisMonthConsumption"]:
                self._attributes["this_month_consumption"][
                    item
                ] = self.client.attributes["thisMonthConsumption"][item]
            self._attributes["previous_month_consumption"] = {}
            for item in self.client.attributes["previousMonthConsumption"]:
                self._attributes["previous_month_consumption"][
                    item
                ] = self.client.attributes["previousMonthConsumption"][item]
            self._attributes["highest_monthly_consumption"] = self.client.attributes[
                "highestMonthlyConsumption"
            ]
            self._attributes["last_year_overall"] = self.client.attributes[
                "lastYearOverAll"
            ]
            self._attributes["this_year_overall"] = self.client.attributes[
                "thisYearOverAll"
            ]
            self._attributes["history"] = {}
            for item in self.client.attributes["history"]:
                self._attributes["history"][item] = self.client.attributes["history"][
                    item
                ]

        except PySuezError:
            self._available = False
            _LOGGER.warning("Unable to fetch data")

    def update(self) -> None:
        """Return the latest collected data from Linky."""
        self._fetch_data()
        _LOGGER.debug("Suez data state is: %s", self._state)
