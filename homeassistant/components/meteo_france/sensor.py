"""Support for Meteo-France raining forecast sensor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from meteofrance_api.helpers import (
    get_warning_text_status_from_indice_color,
    readeable_phenomenoms_dict,
)
from meteofrance_api.model.forecast import Forecast
from meteofrance_api.model.rain import Rain
from meteofrance_api.model.warning import CurrentPhenomenons

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UV_INDEX,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_NEXT_RAIN_1_HOUR_FORECAST,
    ATTR_NEXT_RAIN_DT_REF,
    ATTRIBUTION,
    COORDINATOR_ALERT,
    COORDINATOR_FORECAST,
    COORDINATOR_RAIN,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)

_DataT = TypeVar("_DataT", bound=Rain | Forecast | CurrentPhenomenons)


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
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        data_path="current_forecast:sea_level",
    ),
    MeteoFranceSensorEntityDescription(
        key="wind_gust",
        name="Wind gust",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy-variant",
        entity_registry_enabled_default=False,
        data_path="current_forecast:wind:gust",
    ),
    MeteoFranceSensorEntityDescription(
        key="wind_speed",
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        data_path="current_forecast:wind:speed",
    ),
    MeteoFranceSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
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
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
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
    MeteoFranceSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        data_path="current_forecast:humidity",
    ),
)

SENSOR_TYPES_RAIN: tuple[MeteoFranceSensorEntityDescription, ...] = (
    MeteoFranceSensorEntityDescription(
        key="next_rain",
        name="Next rain",
        device_class=SensorDeviceClass.TIMESTAMP,
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Meteo-France sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator_forecast: DataUpdateCoordinator[Forecast] = data[COORDINATOR_FORECAST]
    coordinator_rain: DataUpdateCoordinator[Rain] | None = data[COORDINATOR_RAIN]
    coordinator_alert: DataUpdateCoordinator[CurrentPhenomenons] | None = data[
        COORDINATOR_ALERT
    ]

    entities: list[MeteoFranceSensor[Any]] = [
        MeteoFranceSensor(coordinator_forecast, description)
        for description in SENSOR_TYPES
    ]
    # Add rain forecast entity only if location support this feature
    if coordinator_rain:
        entities.extend(
            [
                MeteoFranceRainSensor(coordinator_rain, description)
                for description in SENSOR_TYPES_RAIN
            ]
        )
    # Add weather alert entity only if location support this feature
    if coordinator_alert:
        entities.extend(
            [
                MeteoFranceAlertSensor(coordinator_alert, description)
                for description in SENSOR_TYPES_ALERT
            ]
        )
    # Add weather probability entities only if location support this feature
    if coordinator_forecast.data.probability_forecast:
        entities.extend(
            [
                MeteoFranceSensor(coordinator_forecast, description)
                for description in SENSOR_TYPES_PROBABILITY
            ]
        )

    async_add_entities(entities, False)


class MeteoFranceSensor(CoordinatorEntity[DataUpdateCoordinator[_DataT]], SensorEntity):
    """Representation of a Meteo-France sensor."""

    entity_description: MeteoFranceSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[_DataT],
        description: MeteoFranceSensorEntityDescription,
    ) -> None:
        """Initialize the Meteo-France sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if hasattr(coordinator.data, "position"):
            city_name = coordinator.data.position["name"]
            self._attr_name = f"{city_name} {description.name}"
            self._attr_unique_id = f"{coordinator.data.position['lat']},{coordinator.data.position['lon']}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        assert self.platform.config_entry and self.platform.config_entry.unique_id
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.name,
        )

    @property
    def native_value(self):
        """Return the state."""
        path = self.entity_description.data_path.split(":")
        data = getattr(self.coordinator.data, path[0])

        # Specific case for probability forecast
        if path[0] == "probability_forecast":
            if len(path) == 3:
                # This is a fix compared to other entitty as first index is always null in API result for unknown reason
                value = _find_first_probability_forecast_not_null(data, path)
            else:
                value = data[0][path[1]]

        # General case
        elif len(path) == 3:
            value = data[path[1]][path[2]]
        else:
            value = data[path[1]]

        if self.entity_description.key in ("wind_speed", "wind_gust"):
            # convert API wind speed from m/s to km/h
            value = round(value * 3.6)
        return value


class MeteoFranceRainSensor(MeteoFranceSensor[Rain]):
    """Representation of a Meteo-France rain sensor."""

    @property
    def native_value(self):
        """Return the state."""
        # search first cadran with rain
        next_rain = next(
            (cadran for cadran in self.coordinator.data.forecast if cadran["rain"] > 1),
            None,
        )
        return dt_util.utc_from_timestamp(next_rain["dt"]) if next_rain else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        reference_dt = self.coordinator.data.forecast[0]["dt"]
        return {
            ATTR_NEXT_RAIN_DT_REF: dt_util.utc_from_timestamp(reference_dt).isoformat(),
            ATTR_NEXT_RAIN_1_HOUR_FORECAST: {
                f"{int((item['dt'] - reference_dt) / 60)} min": item["desc"]
                for item in self.coordinator.data.forecast
            },
        }


class MeteoFranceAlertSensor(MeteoFranceSensor[CurrentPhenomenons]):
    """Representation of a Meteo-France alert sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[CurrentPhenomenons],
        description: MeteoFranceSensorEntityDescription,
    ) -> None:
        """Initialize the Meteo-France sensor."""
        super().__init__(coordinator, description)
        dept_code = self.coordinator.data.domain_id
        self._attr_name = f"{dept_code} {description.name}"
        self._attr_unique_id = self._attr_name

    @property
    def native_value(self):
        """Return the state."""
        return get_warning_text_status_from_indice_color(
            self.coordinator.data.get_domain_max_color()
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            **readeable_phenomenoms_dict(self.coordinator.data.phenomenons_max_colors),
        }


def _find_first_probability_forecast_not_null(
    probability_forecast: list, path: list
) -> int | None:
    """Search the first not None value in the first forecast elements."""
    for forecast in probability_forecast[0:3]:
        if forecast[path[1]][path[2]] is not None:
            return forecast[path[1]][path[2]]

    # Default return value if no value founded
    return None
