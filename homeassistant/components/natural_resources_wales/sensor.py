"""Platform for sensor integration."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    LENGTH_METERS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

SCAN_INTERVAL = timedelta(seconds=35)
DEFAULT_NAME = "Natural Resources Wales"
DEFAULT_LANGUAGE = "en"
CONF_LANGUAGE = "language"
LANGUAGE_CODES = [
    "en",
    "cy",
]
CONF_MONITORED_STATIONS = "monitored_stations"

ATTR_PROPERTIES = "properties"
ATTR_GEOMETRY = "geometry"
ATTR_COORDINATES = "coordinates"
ATTR_LOCATION = "Location"
ATTR_VALUE = "LatestValue"
ATTR_TIME = "LatestTime"
ATTR_NGR = "NGR"
ATTR_NAME = "Name"
ATTR_PARAM_NAME = "ParamName"
ATTR_STATUS = "Status"
ATTR_TITLE = "Title"
ATTR_NAME = "Name"
ATTR_UNITS = "Units"
ATTR_URL = "url"


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(LANGUAGE_CODES),
        vol.Optional(CONF_MONITORED_STATIONS, default=[]): vol.All(
            cv.ensure_list, [str]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    language = config.get(CONF_LANGUAGE)
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    river_levels_data = NaturalResourcesWalesRiverLevelsData(
        api_key=config.get(CONF_API_KEY, None),
        language=language.upper(),
        interval=interval,
        monitored=config.get(CONF_MONITORED_STATIONS),
    )
    river_levels_data.update()

    if river_levels_data.data is None:
        return

    sensors = []

    for feature in river_levels_data.data:
        if len(river_levels_data.monitored) > 0:
            if (
                not feature[ATTR_PROPERTIES][ATTR_LOCATION]
                in river_levels_data.monitored
            ):
                continue
        sensors.append(NaturalResourcesWalesSensor(river_levels_data, feature))
    add_entities(sensors, True)


class NaturalResourcesWalesSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, river_levels_data, feature):
        """Initialize the sensor."""
        self.river_levels_data = river_levels_data
        self.feature = feature
        self.client_name = self.feature[ATTR_PROPERTIES][
            f"{ATTR_NAME}{self.river_levels_data.language}"
        ]
        self._name = self.feature[ATTR_PROPERTIES][
            f"{ATTR_PARAM_NAME}{self.river_levels_data.language}"
        ]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        name = (
            f"{self._name} {self.client_name}"
            if self.river_levels_data.language == "CY"
            else f"{self.client_name} {self._name}"
        )
        return name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return LENGTH_METERS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_LOCATION: self.feature[ATTR_PROPERTIES][ATTR_LOCATION],
            ATTR_COORDINATES: self.feature[ATTR_GEOMETRY][ATTR_COORDINATES],
            ATTR_VALUE: self.feature[ATTR_PROPERTIES][ATTR_VALUE],
            ATTR_TIME: self.feature[ATTR_PROPERTIES][ATTR_TIME],
            ATTR_NAME: self.feature[ATTR_PROPERTIES][
                f"{ATTR_NAME}{self.river_levels_data.language}"
            ],
            ATTR_NGR: self.feature[ATTR_PROPERTIES][ATTR_NGR],
            ATTR_STATUS: self.feature[ATTR_PROPERTIES][
                f"{ATTR_STATUS}{self.river_levels_data.language}"
            ],
            ATTR_TITLE: self.feature[ATTR_PROPERTIES][
                f"{ATTR_TITLE}{self.river_levels_data.language}"
            ],
            ATTR_UNITS: self.feature[ATTR_PROPERTIES][ATTR_UNITS],
            ATTR_URL: self.feature[ATTR_PROPERTIES][ATTR_URL],
        }

        return attr

    def update(self):
        """Fetch new state data for the sensor."""
        self.river_levels_data.update()
        self._state = self.get_state(self.feature[ATTR_PROPERTIES][ATTR_LOCATION])

    def get_state(self, data):
        """Get state."""
        for feature in self.river_levels_data.data:
            if feature[ATTR_PROPERTIES][ATTR_LOCATION] == data:
                return feature[ATTR_PROPERTIES][ATTR_VALUE]

        return None


class NaturalResourcesWalesRiverLevelsData:
    """Get the latest river levels data from Natural Resources Wales."""

    def __init__(self, api_key, language, interval, monitored):
        """Initialize the data object."""
        self._api_key = api_key
        self.language = language
        self.monitored = monitored

        self.data = None

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest data from Natural Resources Wales."""
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}

        result = requests.get(
            "https://api.naturalresources.wales/riverlevels/v1/all",
            headers=headers,
            timeout=10,
        )
        if "error" in result.json():
            raise ValueError(result.json()["error"]["info"])
        self.data = result.json()["features"]
