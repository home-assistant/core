"""Meteo-France component constants."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)

DOMAIN = "meteo_france"
PLATFORMS = ["sensor", "weather"]
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_RAIN = "coordinator_rain"
COORDINATOR_ALERT = "coordinator_alert"
UNDO_UPDATE_LISTENER = "undo_update_listener"
ATTRIBUTION = "Data provided by Météo-France"
MODEL = "Météo-France mobile API"
MANUFACTURER = "Météo-France"

CONF_CITY = "city"
FORECAST_MODE_HOURLY = "hourly"
FORECAST_MODE_DAILY = "daily"
FORECAST_MODE = [FORECAST_MODE_HOURLY, FORECAST_MODE_DAILY]

ATTR_NEXT_RAIN_1_HOUR_FORECAST = "1_hour_forecast"
ATTR_NEXT_RAIN_DT_REF = "forecast_time_ref"


@dataclass
class MeteoFranceRequiredKeysMixin:
    """Mixin for required keys."""

    data_path: str


@dataclass
class MeteoFranceSensorEntityDescription(
    SensorEntityDescription, MeteoFranceRequiredKeysMixin
):
    """Describes Meteo-France sensor entity."""


SENSOR_TYPES: tuple[MeteoFranceSensorEntityDescription, ...] = (
    MeteoFranceSensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
        entity_registry_enabled_default=False,
        data_path="current_forecast:sea_level",
    ),
    MeteoFranceSensorEntityDescription(
        key="wind_gust",
        name="Wind gust",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy-variant",
        entity_registry_enabled_default=False,
        data_path="current_forecast:wind:gust",
    ),
    MeteoFranceSensorEntityDescription(
        key="wind_speed",
        name="Wind speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        entity_registry_enabled_default=False,
        data_path="current_forecast:wind:speed",
    ),
    MeteoFranceSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_registry_enabled_default=False,
        data_path="current_forecast:T:value",
    ),
    MeteoFranceSensorEntityDescription(
        key="uv",
        name="UV",
        native_unit_of_measurement=UV_INDEX,
        icon="mdi:sunglasses",
        data_path="today_forecast:uv",
    ),
    MeteoFranceSensorEntityDescription(
        key="precipitation",
        name="Daily precipitation",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:cup-water",
        data_path="today_forecast:precipitation:24h",
    ),
    MeteoFranceSensorEntityDescription(
        key="cloud",
        name="Cloud cover",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
        data_path="current_forecast:clouds",
    ),
    MeteoFranceSensorEntityDescription(
        key="original_condition",
        name="Original condition",
        entity_registry_enabled_default=False,
        data_path="current_forecast:weather:desc",
    ),
    MeteoFranceSensorEntityDescription(
        key="daily_original_condition",
        name="Daily original condition",
        entity_registry_enabled_default=False,
        data_path="today_forecast:weather12H:desc",
    ),
)

SENSOR_TYPES_RAIN: tuple[MeteoFranceSensorEntityDescription, ...] = (
    MeteoFranceSensorEntityDescription(
        key="next_rain",
        name="Next rain",
        device_class=DEVICE_CLASS_TIMESTAMP,
        data_path="",
    ),
)

SENSOR_TYPES_ALERT: tuple[MeteoFranceSensorEntityDescription, ...] = (
    MeteoFranceSensorEntityDescription(
        key="weather_alert",
        name="Weather alert",
        icon="mdi:weather-cloudy-alert",
        data_path="",
    ),
)

SENSOR_TYPES_PROBABILITY: tuple[MeteoFranceSensorEntityDescription, ...] = (
    MeteoFranceSensorEntityDescription(
        key="rain_chance",
        name="Rain chance",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        data_path="probability_forecast:rain:3h",
    ),
    MeteoFranceSensorEntityDescription(
        key="snow_chance",
        name="Snow chance",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-snowy",
        data_path="probability_forecast:snow:3h",
    ),
    MeteoFranceSensorEntityDescription(
        key="freeze_chance",
        name="Freeze chance",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:snowflake",
        data_path="probability_forecast:freezing",
    ),
)


CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: ["Nuit Claire", "Nuit claire"],
    ATTR_CONDITION_CLOUDY: ["Très nuageux", "Couvert"],
    ATTR_CONDITION_FOG: [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
        "Bancs de Brouillard",
    ],
    ATTR_CONDITION_HAIL: ["Risque de grêle", "Risque de grèle"],
    ATTR_CONDITION_LIGHTNING: ["Risque d'orages", "Orages"],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Pluie orageuses",
        "Pluies orageuses",
        "Averses orageuses",
    ],
    ATTR_CONDITION_PARTLYCLOUDY: [
        "Ciel voilé",
        "Ciel voilé nuit",
        "Éclaircies",
        "Eclaircies",
        "Peu nuageux",
    ],
    ATTR_CONDITION_POURING: ["Pluie forte"],
    ATTR_CONDITION_RAINY: [
        "Bruine / Pluie faible",
        "Bruine",
        "Pluie faible",
        "Pluies éparses / Rares averses",
        "Pluies éparses",
        "Rares averses",
        "Pluie modérée",
        "Pluie / Averses",
        "Averses",
        "Pluie",
    ],
    ATTR_CONDITION_SNOWY: [
        "Neige / Averses de neige",
        "Neige",
        "Averses de neige",
        "Neige forte",
        "Quelques flocons",
    ],
    ATTR_CONDITION_SNOWY_RAINY: ["Pluie et neige", "Pluie verglaçante"],
    ATTR_CONDITION_SUNNY: ["Ensoleillé"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
