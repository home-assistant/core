"""Support for TMB (Transports Metropolitans de Barcelona) Barcelona public transport."""
from __future__ import annotations

from datetime import timedelta
import logging

from requests import HTTPError
from tmb import IBus
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, TIME_MINUTES
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:bus-clock"

CONF_APP_ID = "app_id"
CONF_APP_KEY = "app_key"
CONF_LINE = "line"
CONF_BUS_STOP = "stop"
CONF_BUS_STOPS = "stops"
ATTR_BUS_STOP = "stop"
ATTR_LINE = "line"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

LINE_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BUS_STOP): cv.string,
        vol.Required(CONF_LINE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_APP_KEY): cv.string,
        vol.Required(CONF_BUS_STOPS): vol.All(cv.ensure_list, [LINE_STOP_SCHEMA]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensors."""
    ibus_client = IBus(config[CONF_APP_ID], config[CONF_APP_KEY])

    sensors = []

    for line_stop in config[CONF_BUS_STOPS]:
        line = line_stop[CONF_LINE]
        stop = line_stop[CONF_BUS_STOP]
        if line_stop.get(CONF_NAME):
            name = f"{line} - {line_stop[CONF_NAME]} ({stop})"
        else:
            name = f"{line} - {stop}"
        sensors.append(TMBSensor(ibus_client, stop, line, name))

    add_entities(sensors, True)


class TMBSensor(SensorEntity):
    """Implementation of a TMB line/stop Sensor."""

    _attr_attribution = "Data provided by Transport Metropolitans de Barcelona"

    def __init__(self, ibus_client, stop, line, name):
        """Initialize the sensor."""
        self._ibus_client = ibus_client
        self._stop = stop
        self._line = line.upper()
        self._name = name
        self._unit = TIME_MINUTES
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._stop}_{self._line}"

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_BUS_STOP: self._stop,
            ATTR_LINE: self._line,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the next bus information."""
        try:
            self._state = self._ibus_client.get_stop_forecast(self._stop, self._line)
        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from TMB API. Please check your API keys are valid"
            )
