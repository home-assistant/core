"""Support for Washington State Department of Transportation (WSDOT) data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
import logging
import re
from typing import Any

import requests
import voluptuous as vol

from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    ATTR_ACCESS_CODE,
    ATTR_AVG_TIME,
    ATTR_CURRENT_TIME,
    ATTR_DESCRIPTION,
    ATTR_NAME,
    ATTR_TIME_UPDATED,
    ATTR_TRAVEL_TIME_ID,
    ATTRIBUTION,
    ICON,
    RESOURCE,
    UnitOfTime,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TRAVEL_TIMES): [
            {vol.Required(CONF_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
        ],
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WSDOT sensor."""
    sensors = []
    for travel_time in entry.data[CONF_TRAVEL_TIMES]:
        name = travel_time.get(CONF_NAME) or travel_time.get(CONF_ID)
        sensors.append(
            WashingtonStateTravelTimeSensor(
                name, entry.data.get(CONF_API_KEY), travel_time.get(CONF_ID)
            )
        )

    add_entities(sensors)


class WashingtonStateTransportSensor(SensorEntity):
    """Sensor that reads the WSDOT web API.

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

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, name, access_code, travel_time_id):
        """Construct a travel time sensor."""
        self._travel_time_id = travel_time_id
        WashingtonStateTransportSensor.__init__(self, name, access_code)

    def update(self) -> None:
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return other details about the sensor state."""
        if self._data is not None:
            attrs = {}
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
        return None


def _parse_wsdot_timestamp(timestamp):
    """Convert WSDOT timestamp to datetime."""
    if not timestamp:
        return None
    # ex: Date(1485040200000-0800)
    milliseconds, tzone = re.search(r"Date\((\d+)([+-]\d\d)\d\d\)", timestamp).groups()
    return datetime.fromtimestamp(
        int(milliseconds) / 1000, tz=timezone(timedelta(hours=int(tzone)))
    )
