"""Support for Dark Sky weather service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Literal, NamedTuple

import forecastio
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEGREE,
    LENGTH_CENTIMETERS,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_MBAR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UV_INDEX,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.unit_system import METRIC_SYSTEM

_LOGGER = logging.getLogger(__name__)

CONF_FORECAST = "forecast"
CONF_HOURLY_FORECAST = "hourly_forecast"
CONF_LANGUAGE = "language"
CONF_UNITS = "units"

DEFAULT_LANGUAGE = "en"
DEFAULT_NAME = "Dark Sky"
SCAN_INTERVAL = timedelta(seconds=300)

DEPRECATED_SENSOR_TYPES = {
    "apparent_temperature_max",
    "apparent_temperature_min",
    "temperature_max",
    "temperature_min",
}

MAP_UNIT_SYSTEM: dict[
    Literal["si", "us", "ca", "uk", "uk2"],
    Literal["si_unit", "us_unit", "ca_unit", "uk_unit", "uk2_unit"],
] = {
    "si": "si_unit",
    "us": "us_unit",
    "ca": "ca_unit",
    "uk": "uk_unit",
    "uk2": "uk2_unit",
}


@dataclass
class DarkskySensorEntityDescription(SensorEntityDescription):
    """Describes Darksky sensor entity."""

    si_unit: str | None = None
    us_unit: str | None = None
    ca_unit: str | None = None
    uk_unit: str | None = None
    uk2_unit: str | None = None
    forecast_mode: list[str] = field(default_factory=list)


SENSOR_TYPES: dict[str, DarkskySensorEntityDescription] = {
    "summary": DarkskySensorEntityDescription(
        key="summary",
        name="Summary",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "minutely_summary": DarkskySensorEntityDescription(
        key="minutely_summary",
        name="Minutely Summary",
        forecast_mode=[],
    ),
    "hourly_summary": DarkskySensorEntityDescription(
        key="hourly_summary",
        name="Hourly Summary",
        forecast_mode=[],
    ),
    "daily_summary": DarkskySensorEntityDescription(
        key="daily_summary",
        name="Daily Summary",
        forecast_mode=[],
    ),
    "icon": DarkskySensorEntityDescription(
        key="icon",
        name="Icon",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "nearest_storm_distance": DarkskySensorEntityDescription(
        key="nearest_storm_distance",
        name="Nearest Storm Distance",
        si_unit=LENGTH_KILOMETERS,
        us_unit=LENGTH_MILES,
        ca_unit=LENGTH_KILOMETERS,
        uk_unit=LENGTH_KILOMETERS,
        uk2_unit=LENGTH_MILES,
        icon="mdi:weather-lightning",
        forecast_mode=["currently"],
    ),
    "nearest_storm_bearing": DarkskySensorEntityDescription(
        key="nearest_storm_bearing",
        name="Nearest Storm Bearing",
        si_unit=DEGREE,
        us_unit=DEGREE,
        ca_unit=DEGREE,
        uk_unit=DEGREE,
        uk2_unit=DEGREE,
        icon="mdi:weather-lightning",
        forecast_mode=["currently"],
    ),
    "precip_type": DarkskySensorEntityDescription(
        key="precip_type",
        name="Precip",
        icon="mdi:weather-pouring",
        forecast_mode=["currently", "minutely", "hourly", "daily"],
    ),
    "precip_intensity": DarkskySensorEntityDescription(
        key="precip_intensity",
        name="Precip Intensity",
        si_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        us_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ca_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        uk_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        uk2_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        icon="mdi:weather-rainy",
        forecast_mode=["currently", "minutely", "hourly", "daily"],
    ),
    "precip_probability": DarkskySensorEntityDescription(
        key="precip_probability",
        name="Precip Probability",
        si_unit=PERCENTAGE,
        us_unit=PERCENTAGE,
        ca_unit=PERCENTAGE,
        uk_unit=PERCENTAGE,
        uk2_unit=PERCENTAGE,
        icon="mdi:water-percent",
        forecast_mode=["currently", "minutely", "hourly", "daily"],
    ),
    "precip_accumulation": DarkskySensorEntityDescription(
        key="precip_accumulation",
        name="Precip Accumulation",
        si_unit=LENGTH_CENTIMETERS,
        us_unit=LENGTH_INCHES,
        ca_unit=LENGTH_CENTIMETERS,
        uk_unit=LENGTH_CENTIMETERS,
        uk2_unit=LENGTH_CENTIMETERS,
        icon="mdi:weather-snowy",
        forecast_mode=["hourly", "daily"],
    ),
    "temperature": DarkskySensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["currently", "hourly"],
    ),
    "apparent_temperature": DarkskySensorEntityDescription(
        key="apparent_temperature",
        name="Apparent Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["currently", "hourly"],
    ),
    "dew_point": DarkskySensorEntityDescription(
        key="dew_point",
        name="Dew Point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "wind_speed": DarkskySensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        si_unit=SPEED_METERS_PER_SECOND,
        us_unit=SPEED_MILES_PER_HOUR,
        ca_unit=SPEED_KILOMETERS_PER_HOUR,
        uk_unit=SPEED_MILES_PER_HOUR,
        uk2_unit=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "wind_bearing": DarkskySensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        si_unit=DEGREE,
        us_unit=DEGREE,
        ca_unit=DEGREE,
        uk_unit=DEGREE,
        uk2_unit=DEGREE,
        icon="mdi:compass",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "wind_gust": DarkskySensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        si_unit=SPEED_METERS_PER_SECOND,
        us_unit=SPEED_MILES_PER_HOUR,
        ca_unit=SPEED_KILOMETERS_PER_HOUR,
        uk_unit=SPEED_MILES_PER_HOUR,
        uk2_unit=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy-variant",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "cloud_cover": DarkskySensorEntityDescription(
        key="cloud_cover",
        name="Cloud Coverage",
        si_unit=PERCENTAGE,
        us_unit=PERCENTAGE,
        ca_unit=PERCENTAGE,
        uk_unit=PERCENTAGE,
        uk2_unit=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "humidity": DarkskySensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        si_unit=PERCENTAGE,
        us_unit=PERCENTAGE,
        ca_unit=PERCENTAGE,
        uk_unit=PERCENTAGE,
        uk2_unit=PERCENTAGE,
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "pressure": DarkskySensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        si_unit=PRESSURE_MBAR,
        us_unit=PRESSURE_MBAR,
        ca_unit=PRESSURE_MBAR,
        uk_unit=PRESSURE_MBAR,
        uk2_unit=PRESSURE_MBAR,
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "visibility": DarkskySensorEntityDescription(
        key="visibility",
        name="Visibility",
        si_unit=LENGTH_KILOMETERS,
        us_unit=LENGTH_MILES,
        ca_unit=LENGTH_KILOMETERS,
        uk_unit=LENGTH_KILOMETERS,
        uk2_unit=LENGTH_MILES,
        icon="mdi:eye",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "ozone": DarkskySensorEntityDescription(
        key="ozone",
        name="Ozone",
        device_class=SensorDeviceClass.OZONE,
        si_unit="DU",
        us_unit="DU",
        ca_unit="DU",
        uk_unit="DU",
        uk2_unit="DU",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "apparent_temperature_max": DarkskySensorEntityDescription(
        key="apparent_temperature_max",
        name="Daily High Apparent Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "apparent_temperature_high": DarkskySensorEntityDescription(
        key="apparent_temperature_high",
        name="Daytime High Apparent Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "apparent_temperature_min": DarkskySensorEntityDescription(
        key="apparent_temperature_min",
        name="Daily Low Apparent Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "apparent_temperature_low": DarkskySensorEntityDescription(
        key="apparent_temperature_low",
        name="Overnight Low Apparent Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "temperature_max": DarkskySensorEntityDescription(
        key="temperature_max",
        name="Daily High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "temperature_high": DarkskySensorEntityDescription(
        key="temperature_high",
        name="Daytime High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "temperature_min": DarkskySensorEntityDescription(
        key="temperature_min",
        name="Daily Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "temperature_low": DarkskySensorEntityDescription(
        key="temperature_low",
        name="Overnight Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        si_unit=TEMP_CELSIUS,
        us_unit=TEMP_FAHRENHEIT,
        ca_unit=TEMP_CELSIUS,
        uk_unit=TEMP_CELSIUS,
        uk2_unit=TEMP_CELSIUS,
        forecast_mode=["daily"],
    ),
    "precip_intensity_max": DarkskySensorEntityDescription(
        key="precip_intensity_max",
        name="Daily Max Precip Intensity",
        si_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        us_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ca_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        uk_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        uk2_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        icon="mdi:thermometer",
        forecast_mode=["daily"],
    ),
    "uv_index": DarkskySensorEntityDescription(
        key="uv_index",
        name="UV Index",
        si_unit=UV_INDEX,
        us_unit=UV_INDEX,
        ca_unit=UV_INDEX,
        uk_unit=UV_INDEX,
        uk2_unit=UV_INDEX,
        icon="mdi:weather-sunny",
        forecast_mode=["currently", "hourly", "daily"],
    ),
    "moon_phase": DarkskySensorEntityDescription(
        key="moon_phase",
        name="Moon Phase",
        icon="mdi:weather-night",
        forecast_mode=["daily"],
    ),
    "sunrise_time": DarkskySensorEntityDescription(
        key="sunrise_time",
        name="Sunrise",
        icon="mdi:white-balance-sunny",
        forecast_mode=["daily"],
    ),
    "sunset_time": DarkskySensorEntityDescription(
        key="sunset_time",
        name="Sunset",
        icon="mdi:weather-night",
        forecast_mode=["daily"],
    ),
    "alerts": DarkskySensorEntityDescription(
        key="alerts",
        name="Alerts",
        icon="mdi:alert-circle-outline",
        forecast_mode=[],
    ),
}


class ConditionPicture(NamedTuple):
    """Entity picture and icon for condition."""

    entity_picture: str
    icon: str


CONDITION_PICTURES: dict[str, ConditionPicture] = {
    "clear-day": ConditionPicture(
        entity_picture="/static/images/darksky/weather-sunny.svg",
        icon="mdi:weather-sunny",
    ),
    "clear-night": ConditionPicture(
        entity_picture="/static/images/darksky/weather-night.svg",
        icon="mdi:weather-night",
    ),
    "rain": ConditionPicture(
        entity_picture="/static/images/darksky/weather-pouring.svg",
        icon="mdi:weather-pouring",
    ),
    "snow": ConditionPicture(
        entity_picture="/static/images/darksky/weather-snowy.svg",
        icon="mdi:weather-snowy",
    ),
    "sleet": ConditionPicture(
        entity_picture="/static/images/darksky/weather-hail.svg",
        icon="mdi:weather-snowy-rainy",
    ),
    "wind": ConditionPicture(
        entity_picture="/static/images/darksky/weather-windy.svg",
        icon="mdi:weather-windy",
    ),
    "fog": ConditionPicture(
        entity_picture="/static/images/darksky/weather-fog.svg",
        icon="mdi:weather-fog",
    ),
    "cloudy": ConditionPicture(
        entity_picture="/static/images/darksky/weather-cloudy.svg",
        icon="mdi:weather-cloudy",
    ),
    "partly-cloudy-day": ConditionPicture(
        entity_picture="/static/images/darksky/weather-partlycloudy.svg",
        icon="mdi:weather-partly-cloudy",
    ),
    "partly-cloudy-night": ConditionPicture(
        entity_picture="/static/images/darksky/weather-cloudy.svg",
        icon="mdi:weather-night-partly-cloudy",
    ),
}

# Language Supported Codes
LANGUAGE_CODES = [
    "ar",
    "az",
    "be",
    "bg",
    "bn",
    "bs",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "ja",
    "ka",
    "kn",
    "ko",
    "eo",
    "es",
    "et",
    "fi",
    "fr",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "kw",
    "lv",
    "ml",
    "mr",
    "nb",
    "nl",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "ta",
    "te",
    "tet",
    "tr",
    "uk",
    "ur",
    "x-pig-latin",
    "zh",
    "zh-tw",
]

ALLOWED_UNITS = ["auto", "si", "us", "ca", "uk", "uk2"]

ALERTS_ATTRS = ["time", "description", "expires", "severity", "uri", "regions", "title"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNITS): vol.In(ALLOWED_UNITS),
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(LANGUAGE_CODES),
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_FORECAST): vol.All(cv.ensure_list, [vol.Range(min=0, max=7)]),
        vol.Optional(CONF_HOURLY_FORECAST): vol.All(
            cv.ensure_list, [vol.Range(min=0, max=48)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dark Sky sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    language = config.get(CONF_LANGUAGE)
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    if CONF_UNITS in config:
        units = config[CONF_UNITS]
    elif hass.config.units is METRIC_SYSTEM:
        units = "si"
    else:
        units = "us"

    forecast_data = DarkSkyData(
        api_key=config.get(CONF_API_KEY),
        latitude=latitude,
        longitude=longitude,
        units=units,
        language=language,
        interval=interval,
    )
    forecast_data.update()
    forecast_data.update_currently()

    # If connection failed don't setup platform.
    if forecast_data.data is None:
        return

    name = config.get(CONF_NAME)

    forecast = config.get(CONF_FORECAST)
    forecast_hour = config.get(CONF_HOURLY_FORECAST)
    sensors: list[SensorEntity] = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        if variable in DEPRECATED_SENSOR_TYPES:
            _LOGGER.warning("Monitored condition %s is deprecated", variable)
        description = SENSOR_TYPES[variable]
        if not description.forecast_mode or "currently" in description.forecast_mode:
            if variable == "alerts":
                sensors.append(DarkSkyAlertSensor(forecast_data, description, name))
            else:
                sensors.append(DarkSkySensor(forecast_data, description, name))

        if forecast is not None and "daily" in description.forecast_mode:
            sensors.extend(
                [
                    DarkSkySensor(
                        forecast_data, description, name, forecast_day=forecast_day
                    )
                    for forecast_day in forecast
                ]
            )
        if forecast_hour is not None and "hourly" in description.forecast_mode:
            sensors.extend(
                [
                    DarkSkySensor(
                        forecast_data, description, name, forecast_hour=forecast_h
                    )
                    for forecast_h in forecast_hour
                ]
            )

    add_entities(sensors, True)


class DarkSkySensor(SensorEntity):
    """Implementation of a Dark Sky sensor."""

    _attr_attribution = "Powered by Dark Sky"
    entity_description: DarkskySensorEntityDescription

    def __init__(
        self,
        forecast_data,
        description: DarkskySensorEntityDescription,
        name,
        forecast_day=None,
        forecast_hour=None,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.forecast_data = forecast_data
        self.forecast_day = forecast_day
        self.forecast_hour = forecast_hour
        self._icon: str | None = None

        if forecast_day is not None:
            self._attr_name = f"{name} {description.name} {forecast_day}d"
        elif forecast_hour is not None:
            self._attr_name = f"{name} {description.name} {forecast_hour}h"
        else:
            self._attr_name = f"{name} {description.name}"

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self.forecast_data.unit_system

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if self._icon is None or "summary" not in self.entity_description.key:
            return None

        if self._icon in CONDITION_PICTURES:
            return CONDITION_PICTURES[self._icon].entity_picture

        return None

    def update_unit_of_measurement(self) -> None:
        """Update units based on unit system."""
        unit_key = MAP_UNIT_SYSTEM.get(self.unit_system, "si_unit")
        self._attr_native_unit_of_measurement = getattr(
            self.entity_description, unit_key
        )

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend, if any."""
        if (
            "summary" in self.entity_description.key
            and self._icon in CONDITION_PICTURES
        ):
            return CONDITION_PICTURES[self._icon].icon

        return self.entity_description.icon

    def update(self) -> None:
        """Get the latest data from Dark Sky and updates the states."""
        # Call the API for new forecast data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits. Note that Dark Sky will
        # charge users for too many calls in 1 day, so take care when updating.
        self.forecast_data.update()
        self.update_unit_of_measurement()

        sensor_type = self.entity_description.key
        if sensor_type == "minutely_summary":
            self.forecast_data.update_minutely()
            minutely = self.forecast_data.data_minutely
            self._attr_native_value = getattr(minutely, "summary", "")
            self._icon = getattr(minutely, "icon", "")
        elif sensor_type == "hourly_summary":
            self.forecast_data.update_hourly()
            hourly = self.forecast_data.data_hourly
            self._attr_native_value = getattr(hourly, "summary", "")
            self._icon = getattr(hourly, "icon", "")
        elif self.forecast_hour is not None:
            self.forecast_data.update_hourly()
            hourly = self.forecast_data.data_hourly
            if hasattr(hourly, "data"):
                self._attr_native_value = self.get_state(
                    hourly.data[self.forecast_hour]
                )
            else:
                self._attr_native_value = 0
        elif sensor_type == "daily_summary":
            self.forecast_data.update_daily()
            daily = self.forecast_data.data_daily
            self._attr_native_value = getattr(daily, "summary", "")
            self._icon = getattr(daily, "icon", "")
        elif self.forecast_day is not None:
            self.forecast_data.update_daily()
            daily = self.forecast_data.data_daily
            if hasattr(daily, "data"):
                self._attr_native_value = self.get_state(daily.data[self.forecast_day])
            else:
                self._attr_native_value = 0
        else:
            self.forecast_data.update_currently()
            currently = self.forecast_data.data_currently
            self._attr_native_value = self.get_state(currently)

    def get_state(self, data):
        """
        Return a new state based on the type.

        If the sensor type is unknown, the current state is returned.
        """
        sensor_type = self.entity_description.key
        lookup_type = convert_to_camel(sensor_type)

        if (state := getattr(data, lookup_type, None)) is None:
            return None

        if "summary" in sensor_type:
            self._icon = getattr(data, "icon", "")

        # Some state data needs to be rounded to whole values or converted to
        # percentages
        if sensor_type in {"precip_probability", "cloud_cover", "humidity"}:
            return round(state * 100, 1)

        if sensor_type in {
            "dew_point",
            "temperature",
            "apparent_temperature",
            "temperature_low",
            "apparent_temperature_low",
            "temperature_min",
            "apparent_temperature_min",
            "temperature_high",
            "apparent_temperature_high",
            "temperature_max",
            "apparent_temperature_max",
            "precip_accumulation",
            "pressure",
            "ozone",
            "uvIndex",
        }:
            return round(state, 1)
        return state


class DarkSkyAlertSensor(SensorEntity):
    """Implementation of a Dark Sky sensor."""

    entity_description: DarkskySensorEntityDescription
    _attr_native_value: int | None

    def __init__(
        self, forecast_data, description: DarkskySensorEntityDescription, name
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.forecast_data = forecast_data
        self._alerts = None

        self._attr_name = f"{name} {description.name}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._attr_native_value is not None and self._attr_native_value > 0:
            return "mdi:alert-circle"
        return "mdi:alert-circle-outline"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._alerts

    def update(self) -> None:
        """Get the latest data from Dark Sky and updates the states."""
        # Call the API for new forecast data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits. Note that Dark Sky will
        # charge users for too many calls in 1 day, so take care when updating.
        self.forecast_data.update()
        self.forecast_data.update_alerts()
        alerts = self.forecast_data.data_alerts
        self._attr_native_value = self.get_state(alerts)

    def get_state(self, data):
        """
        Return a new state based on the type.

        If the sensor type is unknown, the current state is returned.
        """
        alerts = {}
        if data is None:
            self._alerts = alerts
            return data

        multiple_alerts = len(data) > 1
        for i, alert in enumerate(data):
            for attr in ALERTS_ATTRS:
                if multiple_alerts:
                    dkey = f"{attr}_{i!s}"
                else:
                    dkey = attr
                alerts[dkey] = getattr(alert, attr)
        self._alerts = alerts

        return len(data)


def convert_to_camel(data):
    """
    Convert snake case (foo_bar_bat) to camel case (fooBarBat).

    This is not pythonic, but needed for certain situations.
    """
    components = data.split("_")
    capital_components = "".join(x.title() for x in components[1:])
    return f"{components[0]}{capital_components}"


class DarkSkyData:
    """Get the latest data from Darksky."""

    def __init__(self, api_key, latitude, longitude, units, language, interval):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units
        self.language = language
        self._connect_error = False

        self.data = None
        self.unit_system = None
        self.data_currently = None
        self.data_minutely = None
        self.data_hourly = None
        self.data_daily = None
        self.data_alerts = None

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)
        self.update_currently = Throttle(interval)(self._update_currently)
        self.update_minutely = Throttle(interval)(self._update_minutely)
        self.update_hourly = Throttle(interval)(self._update_hourly)
        self.update_daily = Throttle(interval)(self._update_daily)
        self.update_alerts = Throttle(interval)(self._update_alerts)

    def _update(self):
        """Get the latest data from Dark Sky."""
        try:
            self.data = forecastio.load_forecast(
                self._api_key,
                self.latitude,
                self.longitude,
                units=self.units,
                lang=self.language,
            )
            if self._connect_error:
                self._connect_error = False
                _LOGGER.info("Reconnected to Dark Sky")
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error("Unable to connect to Dark Sky: %s", error)
            self.data = None
        self.unit_system = self.data and self.data.json["flags"]["units"]

    def _update_currently(self):
        """Update currently data."""
        self.data_currently = self.data and self.data.currently()

    def _update_minutely(self):
        """Update minutely data."""
        self.data_minutely = self.data and self.data.minutely()

    def _update_hourly(self):
        """Update hourly data."""
        self.data_hourly = self.data and self.data.hourly()

    def _update_daily(self):
        """Update daily data."""
        self.data_daily = self.data and self.data.daily()

    def _update_alerts(self):
        """Update alerts data."""
        self.data_alerts = self.data and self.data.alerts()
