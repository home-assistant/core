"""Support for Meteo-France raining forecast sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from . import ATTRIBUTION, CONF_CITY, DATA_METEO_FRANCE, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_FORECAST = "1h rain forecast"
STATE_ATTR_BULLETIN_TIME = "Bulletin date"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Meteo-France sensor."""
    if discovery_info is None:
        return

    city = discovery_info[CONF_CITY]
    monitored_conditions = discovery_info[CONF_MONITORED_CONDITIONS]
    client = hass.data[DATA_METEO_FRANCE][city]
    weather_alert_client = hass.data[DATA_METEO_FRANCE]["weather_alert_client"]

    from vigilancemeteo import DepartmentWeatherAlert

    alert_watcher = None
    if "weather_alert" in monitored_conditions:
        datas = hass.data[DATA_METEO_FRANCE][city].get_data()
        # Check if a department code is available for this city.
        if "dept" in datas:
            try:
                # If yes create the watcher DepartmentWeatherAlert object.
                alert_watcher = DepartmentWeatherAlert(
                    datas["dept"], weather_alert_client
                )
            except ValueError as exp:
                _LOGGER.error(exp)
                alert_watcher = None
            else:
                _LOGGER.info(
                    "weather alert watcher added for %s" "in department %s",
                    city,
                    datas["dept"],
                )
        else:
            _LOGGER.warning(
                "No dept key found for '%s'. So weather alert "
                "information won't be available",
                city,
            )
            # Exit and don't create the sensor if no department code available.
            return

    add_entities(
        [
            MeteoFranceSensor(variable, client, alert_watcher)
            for variable in monitored_conditions
        ],
        True,
    )


class MeteoFranceSensor(Entity):
    """Representation of a Meteo-France sensor."""

    def __init__(self, condition, client, alert_watcher):
        """Initialize the Meteo-France sensor."""
        self._condition = condition
        self._client = client
        self._alert_watcher = alert_watcher
        self._state = None
        self._data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._data["name"], SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        # Attributes for next_rain sensor.
        if self._condition == "next_rain" and "rain_forecast" in self._data:
            return {
                **{STATE_ATTR_FORECAST: self._data["rain_forecast"]},
                **self._data["next_rain_intervals"],
                **{ATTR_ATTRIBUTION: ATTRIBUTION},
            }

        # Attributes for weather_alert sensor.
        if self._condition == "weather_alert" and self._alert_watcher is not None:
            return {
                **{STATE_ATTR_BULLETIN_TIME: self._alert_watcher.bulletin_date},
                **self._alert_watcher.alerts_list,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }

        # Attributes for all other sensors.
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._client.update()
            self._data = self._client.get_data()

            if self._condition == "weather_alert":
                if self._alert_watcher is not None:
                    self._alert_watcher.update_department_status()
                    self._state = self._alert_watcher.department_color
                    _LOGGER.debug(
                        "weather alert watcher for %s updated. Proxy"
                        " have the status: %s",
                        self._data["name"],
                        self._alert_watcher.proxy.status,
                    )
                else:
                    _LOGGER.warning(
                        "No weather alert data for location %s", self._data["name"]
                    )
            else:
                self._state = self._data[self._condition]
        except KeyError:
            _LOGGER.error(
                "No condition %s for location %s", self._condition, self._data["name"]
            )
            self._state = None
