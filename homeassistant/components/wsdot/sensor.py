"""Support for Washington State Department of Transportation (WSDOT) data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_ACCESS_CODE = "AccessCode"
ATTR_AVG_TIME = "AverageTime"
ATTR_CURRENT_TIME = "CurrentTime"
ATTR_DESCRIPTION = "Description"
ATTR_TIME_UPDATED = "TimeUpdated"
ATTR_TRAVEL_TIME_ID = "TravelTimeID"

ATTRIBUTION = "Data provided by WSDOT"

CONF_TRAVEL_TIMES = "travel_time"

ICON = "mdi:car"

RESOURCE = (
    "http://www.wsdot.wa.gov/Traffic/api/TravelTimes/"
    "TravelTimesREST.svc/GetTravelTimeAsJson"
)

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TRAVEL_TIMES): [
            {vol.Required(CONF_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
        ],
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the WSDOT sensor."""
    sensors = []
    for travel_time in config[CONF_TRAVEL_TIMES]:
        name = travel_time.get(CONF_NAME) or travel_time.get(CONF_ID)
        sensors.append(
            WashingtonStateTravelTimeSensor(
                name, config.get(CONF_API_KEY), travel_time.get(CONF_ID)
            )
        )

    add_entities(sensors, True)


class WashingtonStateTransportSensor(SensorEntity):
    """
    Sensor that reads the WSDOT web API.

    WSDOT provides ferry schedules, toll rates, weather conditions,
    mountain pass conditions, and more. Subclasses of this
    can read them and make them available.
    """

    _attr_icon = ICON

    def __init__(self, name, access_code):
        """Initialize the sensor."""
        self._data = {}
        self._access_code = access_code
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state


class WashingtonStateTravelTimeSensor(WashingtonStateTransportSensor):
    """Travel time sensor from WSDOT."""

    _attr_native_unit_of_measurement = TIME_MINUTES

    def __init__(self, name, access_code, travel_time_id):
        """Construct a travel time sensor."""
        self._travel_time_id = travel_time_id
        WashingtonStateTransportSensor.__init__(self, name, access_code)

    def update(self):
        """Get the latest data from WSDOT."""
        params = {
            ATTR_ACCESS_CODE: self._access_code,
            ATTR_TRAVEL_TIME_ID: self._travel_time_id,
        }

        response = requests.get(RESOURCE, params, timeout=10)
        if response.status_code != HTTPStatus.OK:
            _LOGGER.warning("Invalid response from WSDOT API")
        else:
            self._data = response.json()
        self._state = self._data.get(ATTR_CURRENT_TIME)

    @property
    def extra_state_attributes(self):
        """Return other details about the sensor state."""
        if self._data is not None:
            attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
            for key in (
                ATTR_AVG_TIME,
                ATTR_NAME,
                ATTR_DESCRIPTION,
                ATTR_TRAVEL_TIME_ID,
            ):
                attrs[key] = self._data.get(key)
            attrs[ATTR_TIME_UPDATED] = _parse_wsdot_timestamp(
                self._data.get(ATTR_TIME_UPDATED)
            )
            return attrs


def _parse_wsdot_timestamp(timestamp):
    """Convert WSDOT timestamp to datetime."""
    if not timestamp:
        return None
    # ex: Date(1485040200000-0800)
    milliseconds, tzone = re.search(r"Date\((\d+)([+-]\d\d)\d\d\)", timestamp).groups()
    return datetime.fromtimestamp(
        int(milliseconds) / 1000, tz=timezone(timedelta(hours=int(tzone)))
    )
