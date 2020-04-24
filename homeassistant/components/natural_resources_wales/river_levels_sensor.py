"""Classes for Natural Resources Wales river levels."""
import requests

from homeassistant.const import LENGTH_METERS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

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


class NaturalResourcesWalesRiverLevelsComponent:
    """Natural Resources Wales component to wrap river levels sensors and data."""

    def __init__(self, river_levels_key, language, interval, monitored):
        """Initialize wrapper."""
        self.river_levels_data = NaturalResourcesWalesRiverLevelsData(
            river_levels_key=river_levels_key,
            language=language.upper(),
            interval=interval,
            monitored=monitored,
        )
        self.river_levels_data.update()

    def get_sensors(self):
        """Get array of river level sensors based on monitored stations config."""
        sensors = []

        for feature in self.river_levels_data.data:
            if len(self.river_levels_data.monitored) > 0:
                if (
                    not feature[ATTR_PROPERTIES][ATTR_LOCATION]
                    in self.river_levels_data.monitored
                ):
                    continue
            sensors.append(
                NaturalResourcesWalesRiverLevelsSensor(self.river_levels_data, feature)
            )

        return sensors


class NaturalResourcesWalesRiverLevelsSensor(Entity):
    """Natural Resources Wales River Levels Sensor."""

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

    def __init__(self, river_levels_key, language, interval, monitored):
        """Initialize the data object."""
        self._river_levels_key = river_levels_key
        self.language = language
        self.monitored = monitored

        self.data = None

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest data from Natural Resources Wales."""
        headers = {"Ocp-Apim-Subscription-Key": self._river_levels_key}

        result = requests.get(
            "https://api.naturalresources.wales/riverlevels/v1/all",
            headers=headers,
            timeout=10,
        )
        if "error" in result.json():
            raise ValueError(result.json()["error"]["info"])
        self.data = result.json()["features"]
