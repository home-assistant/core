"""Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
import logging
from typing import Any

from py_rejseplan.api.departures import departuresAPIClient
from py_rejseplan.dataclasses.departure_board import DepartureBoard
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    Decimal,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    StateType,
    UndefinedType,
)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = "stop_id"
ATTR_STOP_NAME = "stop"
ATTR_ROUTE = "route"
ATTR_TYPE = "type"
ATTR_DIRECTION = "direction"
ATTR_FINAL_STOP = "final_stop"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_SCHEDULED_AT = "scheduled_at"
ATTR_REAL_TIME_AT = "real_time_at"
ATTR_TRACK = "track"
ATTR_NEXT_UP = "next_departures"

CONF_AUTHENTICATION = "authentication"
CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DIRECTION = "direction"
CONF_DEPARTURE_TYPE = "departure_type"

DEFAULT_NAME = "Next departure"

SCAN_INTERVAL = timedelta(minutes=5)

BUS_TYPES = ["BUS", "EXB", "TB"]
TRAIN_TYPES = ["LET", "S", "REG", "IC", "LYN", "TOG"]
METRO_TYPES = ["M"]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AUTHENTICATION): cv.string,
        vol.Required(CONF_STOP_ID): vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        # vol.Optional(CONF_ROUTE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        # vol.Optional(CONF_DIRECTION, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DEPARTURE_TYPE, default=[]): vol.All(
            cv.ensure_list, [vol.In([*BUS_TYPES, *TRAIN_TYPES, *METRO_TYPES])]
        ),
    }
)


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format day.month.year hour:minute
    """
    diff = datetime.strptime(timestamp, "%d.%m.%y %H:%M") - dt_util.now().replace(
        tzinfo=None
    )

    return int(diff.total_seconds() // 60)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rejseplanen transport sensor."""
    name = config[CONF_NAME]
    stop_id = config[CONF_STOP_ID]
    # route = config.get(CONF_ROUTE)
    # direction = config[CONF_DIRECTION]
    # departure_type = config[CONF_DEPARTURE_TYPE]
    auth = config[CONF_AUTHENTICATION]

    _LOGGER.debug(
        "Setting up Rejseplanen sensor with stop_id: %s",
        stop_id,
        # route,
        # direction,
    )

    backend = departuresAPIClient(auth_key=auth)
    add_devices([RejseplanenTransportSensor(backend, stop_id, name)], True)


class RejseplanenTransportSensor(SensorEntity):
    """Implementation of Rejseplanen transport sensor."""

    _attr_attribution = "Data provided by rejseplanen.dk"
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        backend: departuresAPIClient,
        stop_id,
        name,
    ) -> None:
        """Initialize the sensor."""
        _LOGGER.debug("Initializing sensor")
        self._backend = backend
        self._name = name
        self._stop_id = stop_id
        self._departure_board: DepartureBoard = None
        self._state = None
        _LOGGER.debug("Sensor initialized")

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(
        self,
    ) -> StateType | str | int | float | None | date | datetime | Decimal:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        if not self._departure_board:
            return {ATTR_STOP_ID: self._stop_id}

        next_up = []
        if len(self._departure_board) > 1:
            next_up = self._departure_board[1:]

        attributes = {
            ATTR_NEXT_UP: next_up,
            ATTR_STOP_ID: self._stop_id,
        }

        if self._departure_board[0] is not None:
            attributes.update(self._departure_board[0])

        return attributes

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    def update(self) -> None:
        """Get the latest data from rejseplanen.dk and update the states."""
        _LOGGER.debug("polling data from Rejseplanen API")
        self._departure_board, _ = self._backend.get_departures(self._stop_id)

        if not self._departure_board or not self._departure_board.departures:
            _LOGGER.debug("No departures found for stop_id: %s", self._stop_id)
            self._state = None
        else:
            _LOGGER.debug("Backend info: %s", self._departure_board)
