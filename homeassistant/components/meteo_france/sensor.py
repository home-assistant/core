"""Support for Meteo-France raining forecast sensor."""
import logging

from meteofrance.client import meteofranceClient
from vigilancemeteo import DepartmentWeatherAlert, VigilanceMeteoFranceProxy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTRIBUTION,
    CONF_CITY,
    DOMAIN,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_ICON,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_FORECAST = "1h rain forecast"
STATE_ATTR_BULLETIN_TIME = "Bulletin date"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France sensor platform."""
    city = entry.data[CONF_CITY]
    client = hass.data[DOMAIN][city]
    weather_alert_client = hass.data[DOMAIN]["weather_alert_client"]

    alert_watcher = None
    datas = client.get_data()
    # Check if a department code is available for this city.
    if "dept" in datas:
        try:
            # If yes create the watcher DepartmentWeatherAlert object.
            alert_watcher = await hass.async_add_executor_job(
                DepartmentWeatherAlert, datas["dept"], weather_alert_client
            )
            _LOGGER.info(
                "Weather alert watcher added for %s in department %s",
                city,
                datas["dept"],
            )
        except ValueError as exp:
            _LOGGER.error(
                "Unexpected error when creating the weather alert sensor for %s in department %s: %s",
                city,
                datas["dept"],
                exp,
            )
    else:
        _LOGGER.warning(
            "No 'dept' key found for '%s'. So weather alert information won't be available",
            city,
        )
        # Exit and don't create the sensor if no department code available.
        return

    async_add_entities(
        [
            MeteoFranceSensor(sensor_type, client, alert_watcher)
            for sensor_type in SENSOR_TYPES
        ],
        True,
    )


class MeteoFranceSensor(Entity):
    """Representation of a Meteo-France sensor."""

    def __init__(
        self,
        sensor_type: str,
        client: meteofranceClient,
        alert_watcher: VigilanceMeteoFranceProxy,
    ):
        """Initialize the Meteo-France sensor."""
        self._type = sensor_type
        self._client = client
        self._alert_watcher = alert_watcher
        self._state = None
        self._data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._data['name']} {SENSOR_TYPES[self._type][SENSOR_TYPE_NAME]}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        # Attributes for next_rain sensor.
        if self._type == "next_rain" and "rain_forecast" in self._data:
            return {
                **{STATE_ATTR_FORECAST: self._data["rain_forecast"]},
                **self._data["next_rain_intervals"],
                **{ATTR_ATTRIBUTION: ATTRIBUTION},
            }

        # Attributes for weather_alert sensor.
        if self._type == "weather_alert" and self._alert_watcher is not None:
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
        return SENSOR_TYPES[self._type][SENSOR_TYPE_UNIT]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_ICON]

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_CLASS]

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._client.update()
            self._data = self._client.get_data()

            if self._type == "weather_alert":
                if self._alert_watcher is not None:
                    self._alert_watcher.update_department_status()
                    self._state = self._alert_watcher.department_color
                    _LOGGER.debug(
                        "weather alert watcher for %s updated. Proxy have the status: %s",
                        self._data["name"],
                        self._alert_watcher.proxy.status,
                    )
                else:
                    _LOGGER.warning(
                        "No weather alert data for location %s", self._data["name"]
                    )
            else:
                self._state = self._data[self._type]
        except KeyError:
            _LOGGER.error(
                "No condition %s for location %s", self._type, self._data["name"]
            )
            self._state = None
