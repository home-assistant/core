"""Support for WUnderground weather service."""
import asyncio
from datetime import timedelta
import logging
import re
from typing import Any, Callable, Optional, Union

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components import sensor
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    DEGREE,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

_RESOURCE = "http://api.wunderground.com/api/{}/{}/{}/q/"
_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by the WUnderground weather service"

CONF_PWS_ID = "pws_id"
CONF_LANG = "lang"

DEFAULT_LANG = "EN"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


# Helper classes for declaring sensor configurations


class WUSensorConfig:
    """WU Sensor Configuration.

    defines basic HA properties of the weather sensor and
    stores callbacks that can parse sensor values out of
    the json data received by WU API.
    """

    def __init__(
        self,
        friendly_name: Union[str, Callable],
        feature: str,
        value: Callable[["WUndergroundData"], Any],
        unit_of_measurement: Optional[str] = None,
        entity_picture=None,
        icon: str = "mdi:gauge",
        device_state_attributes=None,
        device_class=None,
    ):
        """Initialize sensor configuration.

        :param friendly_name: Friendly name
        :param feature: WU feature. See:
                https://www.wunderground.com/weather/api/d/docs?d=data/index
        :param value: callback that extracts desired value from WUndergroundData object
        :param unit_of_measurement: unit of measurement
        :param entity_picture: value or callback returning URL of entity picture
        :param icon: icon name or URL
        :param device_state_attributes: dictionary of attributes, or callable that returns it
        """
        self.friendly_name = friendly_name
        self.unit_of_measurement = unit_of_measurement
        self.feature = feature
        self.value = value
        self.entity_picture = entity_picture
        self.icon = icon
        self.device_state_attributes = device_state_attributes or {}
        self.device_class = device_class


class WUCurrentConditionsSensorConfig(WUSensorConfig):
    """Helper for defining sensor configurations for current conditions."""

    def __init__(
        self,
        friendly_name: Union[str, Callable],
        field: str,
        icon: Optional[str] = "mdi:gauge",
        unit_of_measurement: Optional[str] = None,
        device_class=None,
    ):
        """Initialize current conditions sensor configuration.

        :param friendly_name: Friendly name of sensor
        :field: Field name in the "current_observation" dictionary.
        :icon: icon name or URL, if None sensor will use current weather symbol
        :unit_of_measurement: unit of measurement
        """
        super().__init__(
            friendly_name,
            "conditions",
            value=lambda wu: wu.data["current_observation"][field],
            icon=icon,
            unit_of_measurement=unit_of_measurement,
            entity_picture=lambda wu: wu.data["current_observation"]["icon_url"]
            if icon is None
            else None,
            device_state_attributes={
                "date": lambda wu: wu.data["current_observation"]["observation_time"]
            },
            device_class=device_class,
        )


class WUDailyTextForecastSensorConfig(WUSensorConfig):
    """Helper for defining sensor configurations for daily text forecasts."""

    def __init__(
        self, period: int, field: str, unit_of_measurement: Optional[str] = None
    ):
        """Initialize daily text forecast sensor configuration.

        :param period: forecast period number
        :param field: field name to use as value
        :param unit_of_measurement: unit of measurement
        """
        super().__init__(
            friendly_name=lambda wu: wu.data["forecast"]["txt_forecast"]["forecastday"][
                period
            ]["title"],
            feature="forecast",
            value=lambda wu: wu.data["forecast"]["txt_forecast"]["forecastday"][period][
                field
            ],
            entity_picture=lambda wu: wu.data["forecast"]["txt_forecast"][
                "forecastday"
            ][period]["icon_url"],
            unit_of_measurement=unit_of_measurement,
            device_state_attributes={
                "date": lambda wu: wu.data["forecast"]["txt_forecast"]["date"]
            },
        )


class WUDailySimpleForecastSensorConfig(WUSensorConfig):
    """Helper for defining sensor configurations for daily simpleforecasts."""

    def __init__(
        self,
        friendly_name: str,
        period: int,
        field: str,
        wu_unit: Optional[str] = None,
        ha_unit: Optional[str] = None,
        icon=None,
        device_class=None,
    ):
        """Initialize daily simple forecast sensor configuration.

        :param friendly_name: friendly_name of the sensor
        :param period: forecast period number
        :param field: field name to use as value
        :param wu_unit: "fahrenheit", "celsius", "degrees" etc. see the example json at:
                https://www.wunderground.com/weather/api/d/docs?d=data/forecast&MR=1
        :param ha_unit: corresponding unit in Home Assistant
        """
        super().__init__(
            friendly_name=friendly_name,
            feature="forecast",
            value=(
                lambda wu: wu.data["forecast"]["simpleforecast"]["forecastday"][period][
                    field
                ][wu_unit]
            )
            if wu_unit
            else (
                lambda wu: wu.data["forecast"]["simpleforecast"]["forecastday"][period][
                    field
                ]
            ),
            unit_of_measurement=ha_unit,
            entity_picture=lambda wu: wu.data["forecast"]["simpleforecast"][
                "forecastday"
            ][period]["icon_url"]
            if not icon
            else None,
            icon=icon,
            device_state_attributes={
                "date": lambda wu: wu.data["forecast"]["simpleforecast"]["forecastday"][
                    period
                ]["date"]["pretty"]
            },
            device_class=device_class,
        )


class WUHourlyForecastSensorConfig(WUSensorConfig):
    """Helper for defining sensor configurations for hourly text forecasts."""

    def __init__(self, period: int, field: int):
        """Initialize hourly forecast sensor configuration.

        :param period: forecast period number
        :param field: field name to use as value
        """
        super().__init__(
            friendly_name=lambda wu: (
                f"{wu.data['hourly_forecast'][period]['FCTTIME']['weekday_name_abbrev']} "
                f"{wu.data['hourly_forecast'][period]['FCTTIME']['civil']}"
            ),
            feature="hourly",
            value=lambda wu: wu.data["hourly_forecast"][period][field],
            entity_picture=lambda wu: wu.data["hourly_forecast"][period]["icon_url"],
            device_state_attributes={
                "temp_c": lambda wu: wu.data["hourly_forecast"][period]["temp"][
                    "metric"
                ],
                "temp_f": lambda wu: wu.data["hourly_forecast"][period]["temp"][
                    "english"
                ],
                "dewpoint_c": lambda wu: wu.data["hourly_forecast"][period]["dewpoint"][
                    "metric"
                ],
                "dewpoint_f": lambda wu: wu.data["hourly_forecast"][period]["dewpoint"][
                    "english"
                ],
                "precip_prop": lambda wu: wu.data["hourly_forecast"][period]["pop"],
                "sky": lambda wu: wu.data["hourly_forecast"][period]["sky"],
                "precip_mm": lambda wu: wu.data["hourly_forecast"][period]["qpf"][
                    "metric"
                ],
                "precip_in": lambda wu: wu.data["hourly_forecast"][period]["qpf"][
                    "english"
                ],
                "humidity": lambda wu: wu.data["hourly_forecast"][period]["humidity"],
                "wind_kph": lambda wu: wu.data["hourly_forecast"][period]["wspd"][
                    "metric"
                ],
                "wind_mph": lambda wu: wu.data["hourly_forecast"][period]["wspd"][
                    "english"
                ],
                "pressure_mb": lambda wu: wu.data["hourly_forecast"][period]["mslp"][
                    "metric"
                ],
                "pressure_inHg": lambda wu: wu.data["hourly_forecast"][period]["mslp"][
                    "english"
                ],
                "date": lambda wu: wu.data["hourly_forecast"][period]["FCTTIME"][
                    "pretty"
                ],
            },
        )


class WUAlmanacSensorConfig(WUSensorConfig):
    """Helper for defining field configurations for almanac sensors."""

    def __init__(
        self,
        friendly_name: Union[str, Callable],
        field: str,
        value_type: str,
        wu_unit: str,
        unit_of_measurement: str,
        icon: str,
        device_class=None,
    ):
        """Initialize almanac sensor configuration.

        :param friendly_name: Friendly name
        :param field: value name returned in 'almanac' dict as returned by the WU API
        :param value_type: "record" or "normal"
        :param wu_unit: unit name in WU API
        :param unit_of_measurement: unit of measurement
        :param icon: icon name or URL
        """
        super().__init__(
            friendly_name=friendly_name,
            feature="almanac",
            value=lambda wu: wu.data["almanac"][field][value_type][wu_unit],
            unit_of_measurement=unit_of_measurement,
            icon=icon,
            device_class="temperature",
        )


class WUAlertsSensorConfig(WUSensorConfig):
    """Helper for defining field configuration for alerts."""

    def __init__(self, friendly_name: Union[str, Callable]):
        """Initialiize alerts sensor configuration.

        :param friendly_name: Friendly name
        """
        super().__init__(
            friendly_name=friendly_name,
            feature="alerts",
            value=lambda wu: len(wu.data["alerts"]),
            icon=lambda wu: "mdi:alert-circle-outline"
            if wu.data["alerts"]
            else "mdi:check-circle-outline",
            device_state_attributes=self._get_attributes,
        )

    @staticmethod
    def _get_attributes(rest):

        attrs = {}

        if "alerts" not in rest.data:
            return attrs

        alerts = rest.data["alerts"]
        multiple_alerts = len(alerts) > 1
        for data in alerts:
            for alert in ALERTS_ATTRS:
                if data[alert]:
                    if multiple_alerts:
                        dkey = f"{alert.capitalize()}_{data['type']}"
                    else:
                        dkey = alert.capitalize()
                    attrs[dkey] = data[alert]
        return attrs


# Declaration of supported WU sensors
# (see above helper classes for argument explanation)

SENSOR_TYPES = {
    "alerts": WUAlertsSensorConfig("Alerts"),
    "dewpoint_c": WUCurrentConditionsSensorConfig(
        "Dewpoint", "dewpoint_c", "mdi:water", TEMP_CELSIUS
    ),
    "dewpoint_f": WUCurrentConditionsSensorConfig(
        "Dewpoint", "dewpoint_f", "mdi:water", TEMP_FAHRENHEIT
    ),
    "dewpoint_string": WUCurrentConditionsSensorConfig(
        "Dewpoint Summary", "dewpoint_string", "mdi:water"
    ),
    "feelslike_c": WUCurrentConditionsSensorConfig(
        "Feels Like", "feelslike_c", "mdi:thermometer", TEMP_CELSIUS
    ),
    "feelslike_f": WUCurrentConditionsSensorConfig(
        "Feels Like", "feelslike_f", "mdi:thermometer", TEMP_FAHRENHEIT
    ),
    "feelslike_string": WUCurrentConditionsSensorConfig(
        "Feels Like", "feelslike_string", "mdi:thermometer"
    ),
    "heat_index_c": WUCurrentConditionsSensorConfig(
        "Heat index", "heat_index_c", "mdi:thermometer", TEMP_CELSIUS
    ),
    "heat_index_f": WUCurrentConditionsSensorConfig(
        "Heat index", "heat_index_f", "mdi:thermometer", TEMP_FAHRENHEIT
    ),
    "heat_index_string": WUCurrentConditionsSensorConfig(
        "Heat Index Summary", "heat_index_string", "mdi:thermometer"
    ),
    "elevation": WUSensorConfig(
        "Elevation",
        "conditions",
        value=lambda wu: wu.data["current_observation"]["observation_location"][
            "elevation"
        ].split()[0],
        unit_of_measurement=LENGTH_FEET,
        icon="mdi:elevation-rise",
    ),
    "location": WUSensorConfig(
        "Location",
        "conditions",
        value=lambda wu: wu.data["current_observation"]["display_location"]["full"],
        icon="mdi:map-marker",
    ),
    "observation_time": WUCurrentConditionsSensorConfig(
        "Observation Time", "observation_time", "mdi:clock"
    ),
    "precip_1hr_in": WUCurrentConditionsSensorConfig(
        "Precipitation 1hr", "precip_1hr_in", "mdi:umbrella", LENGTH_INCHES
    ),
    "precip_1hr_metric": WUCurrentConditionsSensorConfig(
        "Precipitation 1hr", "precip_1hr_metric", "mdi:umbrella", "mm"
    ),
    "precip_1hr_string": WUCurrentConditionsSensorConfig(
        "Precipitation 1hr", "precip_1hr_string", "mdi:umbrella"
    ),
    "precip_today_in": WUCurrentConditionsSensorConfig(
        "Precipitation Today", "precip_today_in", "mdi:umbrella", LENGTH_INCHES
    ),
    "precip_today_metric": WUCurrentConditionsSensorConfig(
        "Precipitation Today", "precip_today_metric", "mdi:umbrella", "mm"
    ),
    "precip_today_string": WUCurrentConditionsSensorConfig(
        "Precipitation Today", "precip_today_string", "mdi:umbrella"
    ),
    "pressure_in": WUCurrentConditionsSensorConfig(
        "Pressure", "pressure_in", "mdi:gauge", PRESSURE_INHG, device_class="pressure"
    ),
    "pressure_mb": WUCurrentConditionsSensorConfig(
        "Pressure", "pressure_mb", "mdi:gauge", "mb", device_class="pressure"
    ),
    "pressure_trend": WUCurrentConditionsSensorConfig(
        "Pressure Trend", "pressure_trend", "mdi:gauge", device_class="pressure"
    ),
    "relative_humidity": WUSensorConfig(
        "Relative Humidity",
        "conditions",
        value=lambda wu: int(wu.data["current_observation"]["relative_humidity"][:-1]),
        unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        device_class="humidity",
    ),
    "station_id": WUCurrentConditionsSensorConfig(
        "Station ID", "station_id", "mdi:home"
    ),
    "solarradiation": WUCurrentConditionsSensorConfig(
        "Solar Radiation",
        "solarradiation",
        "mdi:weather-sunny",
        IRRADIATION_WATTS_PER_SQUARE_METER,
    ),
    "temperature_string": WUCurrentConditionsSensorConfig(
        "Temperature Summary", "temperature_string", "mdi:thermometer"
    ),
    "temp_c": WUCurrentConditionsSensorConfig(
        "Temperature",
        "temp_c",
        "mdi:thermometer",
        TEMP_CELSIUS,
        device_class="temperature",
    ),
    "temp_f": WUCurrentConditionsSensorConfig(
        "Temperature",
        "temp_f",
        "mdi:thermometer",
        TEMP_FAHRENHEIT,
        device_class="temperature",
    ),
    "UV": WUCurrentConditionsSensorConfig("UV", "UV", "mdi:sunglasses"),
    "visibility_km": WUCurrentConditionsSensorConfig(
        "Visibility (km)", "visibility_km", "mdi:eye", LENGTH_KILOMETERS
    ),
    "visibility_mi": WUCurrentConditionsSensorConfig(
        "Visibility (miles)", "visibility_mi", "mdi:eye", LENGTH_MILES
    ),
    "weather": WUCurrentConditionsSensorConfig("Weather Summary", "weather", None),
    "wind_degrees": WUCurrentConditionsSensorConfig(
        "Wind Degrees", "wind_degrees", "mdi:weather-windy", DEGREE
    ),
    "wind_dir": WUCurrentConditionsSensorConfig(
        "Wind Direction", "wind_dir", "mdi:weather-windy"
    ),
    "wind_gust_kph": WUCurrentConditionsSensorConfig(
        "Wind Gust", "wind_gust_kph", "mdi:weather-windy", SPEED_KILOMETERS_PER_HOUR
    ),
    "wind_gust_mph": WUCurrentConditionsSensorConfig(
        "Wind Gust", "wind_gust_mph", "mdi:weather-windy", SPEED_MILES_PER_HOUR
    ),
    "wind_kph": WUCurrentConditionsSensorConfig(
        "Wind Speed", "wind_kph", "mdi:weather-windy", SPEED_KILOMETERS_PER_HOUR
    ),
    "wind_mph": WUCurrentConditionsSensorConfig(
        "Wind Speed", "wind_mph", "mdi:weather-windy", SPEED_MILES_PER_HOUR
    ),
    "wind_string": WUCurrentConditionsSensorConfig(
        "Wind Summary", "wind_string", "mdi:weather-windy"
    ),
    "temp_high_record_c": WUAlmanacSensorConfig(
        lambda wu: (
            f"High Temperature Record "
            f"({wu.data['almanac']['temp_high']['recordyear']})"
        ),
        "temp_high",
        "record",
        "C",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ),
    "temp_high_record_f": WUAlmanacSensorConfig(
        lambda wu: (
            f"High Temperature Record "
            f"({wu.data['almanac']['temp_high']['recordyear']})"
        ),
        "temp_high",
        "record",
        "F",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
    ),
    "temp_low_record_c": WUAlmanacSensorConfig(
        lambda wu: (
            f"Low Temperature Record "
            f"({wu.data['almanac']['temp_low']['recordyear']})"
        ),
        "temp_low",
        "record",
        "C",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ),
    "temp_low_record_f": WUAlmanacSensorConfig(
        lambda wu: (
            f"Low Temperature Record "
            f"({wu.data['almanac']['temp_low']['recordyear']})"
        ),
        "temp_low",
        "record",
        "F",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
    ),
    "temp_low_avg_c": WUAlmanacSensorConfig(
        "Historic Average of Low Temperatures for Today",
        "temp_low",
        "normal",
        "C",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ),
    "temp_low_avg_f": WUAlmanacSensorConfig(
        "Historic Average of Low Temperatures for Today",
        "temp_low",
        "normal",
        "F",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
    ),
    "temp_high_avg_c": WUAlmanacSensorConfig(
        "Historic Average of High Temperatures for Today",
        "temp_high",
        "normal",
        "C",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ),
    "temp_high_avg_f": WUAlmanacSensorConfig(
        "Historic Average of High Temperatures for Today",
        "temp_high",
        "normal",
        "F",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
    ),
    "weather_1d": WUDailyTextForecastSensorConfig(0, "fcttext"),
    "weather_1d_metric": WUDailyTextForecastSensorConfig(0, "fcttext_metric"),
    "weather_1n": WUDailyTextForecastSensorConfig(1, "fcttext"),
    "weather_1n_metric": WUDailyTextForecastSensorConfig(1, "fcttext_metric"),
    "weather_2d": WUDailyTextForecastSensorConfig(2, "fcttext"),
    "weather_2d_metric": WUDailyTextForecastSensorConfig(2, "fcttext_metric"),
    "weather_2n": WUDailyTextForecastSensorConfig(3, "fcttext"),
    "weather_2n_metric": WUDailyTextForecastSensorConfig(3, "fcttext_metric"),
    "weather_3d": WUDailyTextForecastSensorConfig(4, "fcttext"),
    "weather_3d_metric": WUDailyTextForecastSensorConfig(4, "fcttext_metric"),
    "weather_3n": WUDailyTextForecastSensorConfig(5, "fcttext"),
    "weather_3n_metric": WUDailyTextForecastSensorConfig(5, "fcttext_metric"),
    "weather_4d": WUDailyTextForecastSensorConfig(6, "fcttext"),
    "weather_4d_metric": WUDailyTextForecastSensorConfig(6, "fcttext_metric"),
    "weather_4n": WUDailyTextForecastSensorConfig(7, "fcttext"),
    "weather_4n_metric": WUDailyTextForecastSensorConfig(7, "fcttext_metric"),
    "weather_1h": WUHourlyForecastSensorConfig(0, "condition"),
    "weather_2h": WUHourlyForecastSensorConfig(1, "condition"),
    "weather_3h": WUHourlyForecastSensorConfig(2, "condition"),
    "weather_4h": WUHourlyForecastSensorConfig(3, "condition"),
    "weather_5h": WUHourlyForecastSensorConfig(4, "condition"),
    "weather_6h": WUHourlyForecastSensorConfig(5, "condition"),
    "weather_7h": WUHourlyForecastSensorConfig(6, "condition"),
    "weather_8h": WUHourlyForecastSensorConfig(7, "condition"),
    "weather_9h": WUHourlyForecastSensorConfig(8, "condition"),
    "weather_10h": WUHourlyForecastSensorConfig(9, "condition"),
    "weather_11h": WUHourlyForecastSensorConfig(10, "condition"),
    "weather_12h": WUHourlyForecastSensorConfig(11, "condition"),
    "weather_13h": WUHourlyForecastSensorConfig(12, "condition"),
    "weather_14h": WUHourlyForecastSensorConfig(13, "condition"),
    "weather_15h": WUHourlyForecastSensorConfig(14, "condition"),
    "weather_16h": WUHourlyForecastSensorConfig(15, "condition"),
    "weather_17h": WUHourlyForecastSensorConfig(16, "condition"),
    "weather_18h": WUHourlyForecastSensorConfig(17, "condition"),
    "weather_19h": WUHourlyForecastSensorConfig(18, "condition"),
    "weather_20h": WUHourlyForecastSensorConfig(19, "condition"),
    "weather_21h": WUHourlyForecastSensorConfig(20, "condition"),
    "weather_22h": WUHourlyForecastSensorConfig(21, "condition"),
    "weather_23h": WUHourlyForecastSensorConfig(22, "condition"),
    "weather_24h": WUHourlyForecastSensorConfig(23, "condition"),
    "weather_25h": WUHourlyForecastSensorConfig(24, "condition"),
    "weather_26h": WUHourlyForecastSensorConfig(25, "condition"),
    "weather_27h": WUHourlyForecastSensorConfig(26, "condition"),
    "weather_28h": WUHourlyForecastSensorConfig(27, "condition"),
    "weather_29h": WUHourlyForecastSensorConfig(28, "condition"),
    "weather_30h": WUHourlyForecastSensorConfig(29, "condition"),
    "weather_31h": WUHourlyForecastSensorConfig(30, "condition"),
    "weather_32h": WUHourlyForecastSensorConfig(31, "condition"),
    "weather_33h": WUHourlyForecastSensorConfig(32, "condition"),
    "weather_34h": WUHourlyForecastSensorConfig(33, "condition"),
    "weather_35h": WUHourlyForecastSensorConfig(34, "condition"),
    "weather_36h": WUHourlyForecastSensorConfig(35, "condition"),
    "temp_high_1d_c": WUDailySimpleForecastSensorConfig(
        "High Temperature Today",
        0,
        "high",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_2d_c": WUDailySimpleForecastSensorConfig(
        "High Temperature Tomorrow",
        1,
        "high",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_3d_c": WUDailySimpleForecastSensorConfig(
        "High Temperature in 3 Days",
        2,
        "high",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_4d_c": WUDailySimpleForecastSensorConfig(
        "High Temperature in 4 Days",
        3,
        "high",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_1d_f": WUDailySimpleForecastSensorConfig(
        "High Temperature Today",
        0,
        "high",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_2d_f": WUDailySimpleForecastSensorConfig(
        "High Temperature Tomorrow",
        1,
        "high",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_3d_f": WUDailySimpleForecastSensorConfig(
        "High Temperature in 3 Days",
        2,
        "high",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_high_4d_f": WUDailySimpleForecastSensorConfig(
        "High Temperature in 4 Days",
        3,
        "high",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_1d_c": WUDailySimpleForecastSensorConfig(
        "Low Temperature Today",
        0,
        "low",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_2d_c": WUDailySimpleForecastSensorConfig(
        "Low Temperature Tomorrow",
        1,
        "low",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_3d_c": WUDailySimpleForecastSensorConfig(
        "Low Temperature in 3 Days",
        2,
        "low",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_4d_c": WUDailySimpleForecastSensorConfig(
        "Low Temperature in 4 Days",
        3,
        "low",
        "celsius",
        TEMP_CELSIUS,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_1d_f": WUDailySimpleForecastSensorConfig(
        "Low Temperature Today",
        0,
        "low",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_2d_f": WUDailySimpleForecastSensorConfig(
        "Low Temperature Tomorrow",
        1,
        "low",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_3d_f": WUDailySimpleForecastSensorConfig(
        "Low Temperature in 3 Days",
        2,
        "low",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "temp_low_4d_f": WUDailySimpleForecastSensorConfig(
        "Low Temperature in 4 Days",
        3,
        "low",
        "fahrenheit",
        TEMP_FAHRENHEIT,
        "mdi:thermometer",
        device_class="temperature",
    ),
    "wind_gust_1d_kph": WUDailySimpleForecastSensorConfig(
        "Max. Wind Today",
        0,
        "maxwind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_2d_kph": WUDailySimpleForecastSensorConfig(
        "Max. Wind Tomorrow",
        1,
        "maxwind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_3d_kph": WUDailySimpleForecastSensorConfig(
        "Max. Wind in 3 Days",
        2,
        "maxwind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_4d_kph": WUDailySimpleForecastSensorConfig(
        "Max. Wind in 4 Days",
        3,
        "maxwind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_1d_mph": WUDailySimpleForecastSensorConfig(
        "Max. Wind Today",
        0,
        "maxwind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_2d_mph": WUDailySimpleForecastSensorConfig(
        "Max. Wind Tomorrow",
        1,
        "maxwind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_3d_mph": WUDailySimpleForecastSensorConfig(
        "Max. Wind in 3 Days",
        2,
        "maxwind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_gust_4d_mph": WUDailySimpleForecastSensorConfig(
        "Max. Wind in 4 Days",
        3,
        "maxwind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_1d_kph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind Today",
        0,
        "avewind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_2d_kph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind Tomorrow",
        1,
        "avewind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_3d_kph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind in 3 Days",
        2,
        "avewind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_4d_kph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind in 4 Days",
        3,
        "avewind",
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_1d_mph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind Today",
        0,
        "avewind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_2d_mph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind Tomorrow",
        1,
        "avewind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_3d_mph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind in 3 Days",
        2,
        "avewind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "wind_4d_mph": WUDailySimpleForecastSensorConfig(
        "Avg. Wind in 4 Days",
        3,
        "avewind",
        SPEED_MILES_PER_HOUR,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
    ),
    "precip_1d_mm": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity Today", 0, "qpf_allday", "mm", "mm", "mdi:umbrella"
    ),
    "precip_2d_mm": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity Tomorrow", 1, "qpf_allday", "mm", "mm", "mdi:umbrella"
    ),
    "precip_3d_mm": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity in 3 Days", 2, "qpf_allday", "mm", "mm", "mdi:umbrella"
    ),
    "precip_4d_mm": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity in 4 Days", 3, "qpf_allday", "mm", "mm", "mdi:umbrella"
    ),
    "precip_1d_in": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity Today",
        0,
        "qpf_allday",
        "in",
        LENGTH_INCHES,
        "mdi:umbrella",
    ),
    "precip_2d_in": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity Tomorrow",
        1,
        "qpf_allday",
        "in",
        LENGTH_INCHES,
        "mdi:umbrella",
    ),
    "precip_3d_in": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity in 3 Days",
        2,
        "qpf_allday",
        "in",
        LENGTH_INCHES,
        "mdi:umbrella",
    ),
    "precip_4d_in": WUDailySimpleForecastSensorConfig(
        "Precipitation Intensity in 4 Days",
        3,
        "qpf_allday",
        "in",
        LENGTH_INCHES,
        "mdi:umbrella",
    ),
    "precip_1d": WUDailySimpleForecastSensorConfig(
        "Precipitation Probability Today",
        0,
        "pop",
        None,
        PERCENTAGE,
        "mdi:umbrella",
    ),
    "precip_2d": WUDailySimpleForecastSensorConfig(
        "Precipitation Probability Tomorrow",
        1,
        "pop",
        None,
        PERCENTAGE,
        "mdi:umbrella",
    ),
    "precip_3d": WUDailySimpleForecastSensorConfig(
        "Precipitation Probability in 3 Days",
        2,
        "pop",
        None,
        PERCENTAGE,
        "mdi:umbrella",
    ),
    "precip_4d": WUDailySimpleForecastSensorConfig(
        "Precipitation Probability in 4 Days",
        3,
        "pop",
        None,
        PERCENTAGE,
        "mdi:umbrella",
    ),
}

# Alert Attributes
ALERTS_ATTRS = ["date", "description", "expires", "message"]

# Language Supported Codes
LANG_CODES = [
    "AF",
    "AL",
    "AR",
    "HY",
    "AZ",
    "EU",
    "BY",
    "BU",
    "LI",
    "MY",
    "CA",
    "CN",
    "TW",
    "CR",
    "CZ",
    "DK",
    "DV",
    "NL",
    "EN",
    "EO",
    "ET",
    "FA",
    "FI",
    "FR",
    "FC",
    "GZ",
    "DL",
    "KA",
    "GR",
    "GU",
    "HT",
    "IL",
    "HI",
    "HU",
    "IS",
    "IO",
    "ID",
    "IR",
    "IT",
    "JP",
    "JW",
    "KM",
    "KR",
    "KU",
    "LA",
    "LV",
    "LT",
    "ND",
    "MK",
    "MT",
    "GM",
    "MI",
    "MR",
    "MN",
    "NO",
    "OC",
    "PS",
    "GN",
    "PL",
    "BR",
    "PA",
    "RO",
    "RU",
    "SR",
    "SK",
    "SL",
    "SP",
    "SI",
    "SW",
    "CH",
    "TL",
    "TT",
    "TH",
    "TR",
    "TK",
    "UA",
    "UZ",
    "VU",
    "CY",
    "SN",
    "JI",
    "YI",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PWS_ID): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.All(vol.In(LANG_CODES)),
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up the WUnderground sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    pws_id = config.get(CONF_PWS_ID)

    rest = WUndergroundData(
        hass,
        config.get(CONF_API_KEY),
        pws_id,
        config.get(CONF_LANG),
        latitude,
        longitude,
    )

    if pws_id is None:
        unique_id_base = f"@{longitude:06f},{latitude:06f}"
    else:
        # Manually specified weather station, use that for unique_id
        unique_id_base = pws_id
    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(WUndergroundSensor(hass, rest, variable, unique_id_base))

    await rest.async_update()
    if not rest.data:
        raise PlatformNotReady

    async_add_entities(sensors, True)


class WUndergroundSensor(Entity):
    """Implementing the WUnderground sensor."""

    def __init__(self, hass: HomeAssistantType, rest, condition, unique_id_base: str):
        """Initialize the sensor."""
        self.rest = rest
        self._condition = condition
        self._state = None
        self._attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._icon = None
        self._entity_picture = None
        self._unit_of_measurement = self._cfg_expand("unit_of_measurement")
        self.rest.request_feature(SENSOR_TYPES[condition].feature)
        # This is only the suggested entity id, it might get changed by
        # the entity registry later.
        self.entity_id = sensor.ENTITY_ID_FORMAT.format(f"pws_{condition}")
        self._unique_id = f"{unique_id_base},{condition}"
        self._device_class = self._cfg_expand("device_class")

    def _cfg_expand(self, what, default=None):
        """Parse and return sensor data."""
        cfg = SENSOR_TYPES[self._condition]
        val = getattr(cfg, what)
        if not callable(val):
            return val
        try:
            val = val(self.rest)
        except (KeyError, IndexError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Failed to expand cfg from WU API. Condition: %s Attr: %s Error: %s",
                self._condition,
                what,
                repr(err),
            )
            val = default

        return val

    def _update_attrs(self):
        """Parse and update device state attributes."""
        attrs = self._cfg_expand("device_state_attributes", {})

        for (attr, callback) in attrs.items():
            if callable(callback):
                try:
                    self._attributes[attr] = callback(self.rest)
                except (KeyError, IndexError, TypeError, ValueError) as err:
                    _LOGGER.warning(
                        "Failed to update attrs from WU API."
                        " Condition: %s Attr: %s Error: %s",
                        self._condition,
                        attr,
                        repr(err),
                    )
            else:
                self._attributes[attr] = callback

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._cfg_expand("friendly_name")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture."""
        return self._entity_picture

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the units of measurement."""
        return self._device_class

    async def async_update(self):
        """Update current conditions."""
        await self.rest.async_update()

        if not self.rest.data:
            # no data, return
            return

        self._state = self._cfg_expand("value")
        self._update_attrs()
        self._icon = self._cfg_expand("icon", super().icon)
        url = self._cfg_expand("entity_picture")
        if isinstance(url, str):
            self._entity_picture = re.sub(
                r"^http://", "https://", url, flags=re.IGNORECASE
            )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id


class WUndergroundData:
    """Get data from WUnderground."""

    def __init__(self, hass, api_key, pws_id, lang, latitude, longitude):
        """Initialize the data object."""
        self._hass = hass
        self._api_key = api_key
        self._pws_id = pws_id
        self._lang = f"lang:{lang}"
        self._latitude = latitude
        self._longitude = longitude
        self._features = set()
        self.data = None
        self._session = async_get_clientsession(self._hass)

    def request_feature(self, feature):
        """Register feature to be fetched from WU API."""
        self._features.add(feature)

    def _build_url(self, baseurl=_RESOURCE):
        url = baseurl.format(
            self._api_key, "/".join(sorted(self._features)), self._lang
        )
        if self._pws_id:
            url = f"{url}pws:{self._pws_id}"
        else:
            url = f"{url}{self._latitude},{self._longitude}"

        return f"{url}.json"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from WUnderground."""
        try:
            with async_timeout.timeout(10):
                response = await self._session.get(self._build_url())
            result = await response.json()
            if "error" in result["response"]:
                raise ValueError(result["response"]["error"]["description"])
            self.data = result
        except ValueError as err:
            _LOGGER.error("Check WUnderground API %s", err.args)
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching WUnderground data: %s", repr(err))
