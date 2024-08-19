"""Support for departure information for public transport in Munich."""

# mypy: ignore-errors
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import logging

import MVGLive
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_DEPARTURE = "nextdeparture"

CONF_STATION = "station"
CONF_DESTINATIONS = "destinations"
CONF_DIRECTIONS = "directions"
CONF_LINES = "lines"
CONF_PRODUCTS = "products"
CONF_TIMEOFFSET = "timeoffset"
CONF_NUMBER = "number"

DEFAULT_PRODUCT = ["U-Bahn", "Tram", "Bus", "ExpressBus", "S-Bahn", "Nachteule"]

ICONS = {
    "U-Bahn": "mdi:subway",
    "Tram": "mdi:tram",
    "Bus": "mdi:bus",
    "ExpressBus": "mdi:bus",
    "S-Bahn": "mdi:train",
    "Nachteule": "mdi:owl",
    "SEV": "mdi:checkbox-blank-circle-outline",
    "-": "mdi:clock",
}
ATTRIBUTION = "Data provided by MVG-live.de"

SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STATION): cv.string,
                vol.Optional(CONF_DESTINATIONS, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_DIRECTIONS, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_LINES, default=[""]): cv.ensure_list_csv,
                vol.Optional(
                    CONF_PRODUCTS, default=DEFAULT_PRODUCT
                ): cv.ensure_list_csv,
                vol.Optional(CONF_TIMEOFFSET, default=0): cv.positive_int,
                vol.Optional(CONF_NUMBER, default=1): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
            }
        ]
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MVGLive sensor."""
    add_entities(
        (
            MVGLiveSensor(
                nextdeparture.get(CONF_STATION),
                nextdeparture.get(CONF_DESTINATIONS),
                nextdeparture.get(CONF_DIRECTIONS),
                nextdeparture.get(CONF_LINES),
                nextdeparture.get(CONF_PRODUCTS),
                nextdeparture.get(CONF_TIMEOFFSET),
                nextdeparture.get(CONF_NUMBER),
                nextdeparture.get(CONF_NAME),
            )
            for nextdeparture in config[CONF_NEXT_DEPARTURE]
        ),
        True,
    )


class MVGLiveSensor(SensorEntity):
    """Implementation of an MVG Live sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        station,
        destinations,
        directions,
        lines,
        products,
        timeoffset,
        number,
        name,
    ):
        """Initialize the sensor."""
        self._station = station
        self._name = name
        self.data = MVGLiveData(
            station, destinations, directions, lines, products, timeoffset, number
        )
        self._state = None
        self._icon = ICONS["-"]

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._name:
            return self._name
        return self._station

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not (dep := self.data.departures):
            return None
        attr = dep[0]  # next depature attributes
        attr["departures"] = deepcopy(dep)  # all departures dictionary
        return attr

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    def update(self) -> None:
        """Get the latest data and update the state."""
        self.data.update()
        if not self.data.departures:
            self._state = "-"
            self._icon = ICONS["-"]
        else:
            self._state = self.data.departures[0].get("time", "-")
            self._icon = ICONS[self.data.departures[0].get("product", "-")]


class MVGLiveData:
    """Pull data from the mvg-live.de web page."""

    def __init__(
        self, station, destinations, directions, lines, products, timeoffset, number
    ):
        """Initialize the sensor."""
        self._station = station
        self._destinations = destinations
        self._directions = directions
        self._lines = lines
        self._products = products
        self._timeoffset = timeoffset
        self._number = number
        self._include_ubahn = "U-Bahn" in self._products
        self._include_tram = "Tram" in self._products
        self._include_bus = "Bus" in self._products
        self._include_sbahn = "S-Bahn" in self._products
        self.mvg = MVGLive.MVGLive()
        self.departures = []

    def update(self):
        """Update the connection data."""
        try:
            _departures = self.mvg.getlivedata(
                station=self._station,
                timeoffset=self._timeoffset,
                ubahn=self._include_ubahn,
                tram=self._include_tram,
                bus=self._include_bus,
                sbahn=self._include_sbahn,
            )
        except ValueError:
            self.departures = []
            _LOGGER.warning("Returned data not understood")
            return
        self.departures = []
        for i, _departure in enumerate(_departures):
            # find the first departure meeting the criteria
            if (
                "" not in self._destinations[:1]
                and _departure["destination"] not in self._destinations
            ):
                continue

            if (
                "" not in self._directions[:1]
                and _departure["direction"] not in self._directions
            ):
                continue

            if "" not in self._lines[:1] and _departure["linename"] not in self._lines:
                continue

            if _departure["time"] < self._timeoffset:
                continue

            # now select the relevant data
            _nextdep = {}
            for k in ("destination", "linename", "time", "direction", "product"):
                _nextdep[k] = _departure.get(k, "")
            _nextdep["time"] = int(_nextdep["time"])
            self.departures.append(_nextdep)
            if i == self._number - 1:
                break
