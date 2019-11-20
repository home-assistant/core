"""Support for the HERE Destination Weather service."""
from datetime import timedelta
import logging
from typing import Callable, Dict, Optional, Union

import herepy
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import (
    HEREWeatherData,
    convert_unit_of_measurement_if_needed,
    get_attribute_from_here_data,
)
from .const import (
    CONF_APP_CODE,
    CONF_APP_ID,
    CONF_LOCATION_NAME,
    CONF_MODES,
    CONF_OFFSET,
    CONF_ZIP_CODE,
    DEFAULT_MODE,
    DEFAULT_NAME,
    SENSOR_TYPES,
)

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_APP_CODE): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Exclusive(CONF_LATITUDE, "coords_or_name_or_zip_code"): cv.latitude,
        vol.Exclusive(CONF_LOCATION_NAME, "coords_or_name_or_zip_code"): cv.string,
        vol.Exclusive(CONF_ZIP_CODE, "coords_or_name_or_zip_code"): cv.string,
        vol.Optional(CONF_OFFSET, default=0): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(CONF_MODES),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_LOCATION_NAME): cv.string,
        vol.Optional(CONF_ZIP_CODE): cv.string,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: None = None,
) -> None:
    """Set up the HERE Destination Weather sensor."""
    app_id = config[CONF_APP_ID]
    app_code = config[CONF_APP_CODE]

    here_client = herepy.DestinationWeatherApi(app_id, app_code)

    if not await hass.async_add_executor_job(
        _are_valid_client_credentials, here_client
    ):
        _LOGGER.error(
            "Invalid credentials. This error is returned if the specified token was invalid or no contract could be found for this token."
        )
        return

    name = config.get(CONF_NAME)
    mode = config[CONF_MODE]
    offset = config[CONF_OFFSET]
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    location_name = config.get(CONF_LOCATION_NAME)
    zip_code = config.get(CONF_ZIP_CODE)
    units = config.get(CONF_UNIT_SYSTEM, hass.config.units.name)

    here_data = HEREWeatherData(
        here_client, mode, units, latitude, longitude, location_name, zip_code
    )
    sensors_to_add = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type == mode:
            for weather_attribute in SENSOR_TYPES[sensor_type]:
                sensors_to_add.append(
                    HEREDestinationWeatherSensor(
                        name, here_data, sensor_type, offset, weather_attribute
                    )
                )
    async_add_entities(sensors_to_add, True)


def _are_valid_client_credentials(here_client: herepy.DestinationWeatherApi) -> bool:
    """Check if the provided credentials are correct using defaults."""
    try:
        product = herepy.WeatherProductType.forecast_astronomy
        known_good_zip_code = "10025"
        here_client.weather_for_zip_code(known_good_zip_code, product)
    except herepy.UnauthorizedError:
        return False
    return True


class HEREDestinationWeatherSensor(Entity):
    """Implementation of an HERE Destination Weather sensor."""

    def __init__(
        self,
        name: str,
        here_data: "HEREWeatherData",
        sensor_type: str,
        sensor_number: int,
        weather_attribute: str,
    ) -> None:
        """Initialize the sensor."""
        self._base_name = name
        self._name_suffix = SENSOR_TYPES[sensor_type][weather_attribute]["name"]
        self._here_data = here_data
        self._sensor_type = sensor_type
        self._sensor_number = sensor_number
        self._weather_attribute = weather_attribute
        self._unit_of_measurement = convert_unit_of_measurement_if_needed(
            self._here_data.units,
            SENSOR_TYPES[sensor_type][weather_attribute]["unit_of_measurement"],
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._base_name} {self._name_suffix}"

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return get_attribute_from_here_data(
            self._here_data.data, self._weather_attribute, self._sensor_number
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(
        self,
    ) -> Optional[Dict[str, Union[None, float, str, bool]]]:
        """Return the state attributes."""
        return None

    async def async_update(self) -> None:
        """Get the latest data from HERE."""
        await self.hass.async_add_executor_job(self._here_data.update)
