"""Support for Transport NSW (AU) to query next leave event."""
from __future__ import annotations

from datetime import timedelta

from TransportNSW import TransportNSW
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_MODE,
    CONF_API_KEY,
    CONF_NAME,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_STOP_ID = "stop_id"
ATTR_ROUTE = "route"
ATTR_DUE_IN = "due"
ATTR_DELAY = "delay"
ATTR_REAL_TIME = "real_time"
ATTR_DESTINATION = "destination"

ATTRIBUTION = "Data provided by Transport NSW"

CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DESTINATION = "destination"

DEFAULT_NAME = "Next Bus"
ICONS = {
    "Train": "mdi:train",
    "Lightrail": "mdi:tram",
    "Bus": "mdi:bus",
    "Coach": "mdi:bus",
    "Ferry": "mdi:ferry",
    "Schoolbus": "mdi:bus",
    "n/a": "mdi:clock",
    None: "mdi:clock",
}

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUTE, default=""): cv.string,
        vol.Optional(CONF_DESTINATION, default=""): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Transport NSW sensor."""
    stop_id = config[CONF_STOP_ID]
    api_key = config[CONF_API_KEY]
    route = config.get(CONF_ROUTE)
    destination = config.get(CONF_DESTINATION)
    name = config.get(CONF_NAME)

    data = PublicTransportData(stop_id, route, destination, api_key)
    add_entities([TransportNSWSensor(data, stop_id, name)], True)


class TransportNSWSensor(SensorEntity):
    """Implementation of an Transport NSW sensor."""

    def __init__(self, data, stop_id, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop_id = stop_id
        self._times = self._state = None
        self._icon = ICONS[None]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._times is not None:
            return {
                ATTR_DUE_IN: self._times[ATTR_DUE_IN],
                ATTR_STOP_ID: self._stop_id,
                ATTR_ROUTE: self._times[ATTR_ROUTE],
                ATTR_DELAY: self._times[ATTR_DELAY],
                ATTR_REAL_TIME: self._times[ATTR_REAL_TIME],
                ATTR_DESTINATION: self._times[ATTR_DESTINATION],
                ATTR_MODE: self._times[ATTR_MODE],
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data from Transport NSW and update the states."""
        self.data.update()
        self._times = self.data.info
        self._state = self._times[ATTR_DUE_IN]
        self._icon = ICONS[self._times[ATTR_MODE]]


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, stop_id, route, destination, api_key):
        """Initialize the data object."""
        self._stop_id = stop_id
        self._route = route
        self._destination = destination
        self._api_key = api_key
        self.info = {
            ATTR_ROUTE: self._route,
            ATTR_DUE_IN: "n/a",
            ATTR_DELAY: "n/a",
            ATTR_REAL_TIME: "n/a",
            ATTR_DESTINATION: "n/a",
            ATTR_MODE: None,
        }
        self.tnsw = TransportNSW()

    def update(self):
        """Get the next leave time."""
        _data = self.tnsw.get_departures(
            self._stop_id, self._route, self._destination, self._api_key
        )
        self.info = {
            ATTR_ROUTE: _data["route"],
            ATTR_DUE_IN: _data["due"],
            ATTR_DELAY: _data["delay"],
            ATTR_REAL_TIME: _data["real_time"],
            ATTR_DESTINATION: _data["destination"],
            ATTR_MODE: _data["mode"],
        }
