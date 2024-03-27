"""Sensors for cloud based weatherflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from weatherflow4py.models.rest.unified import WeatherFlowData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import WeatherFlowCloudDataUpdateCoordinator
from .entity import WeatherFlowCloudEntity


@dataclass(frozen=True, kw_only=True)
class WeatherFlowCloudSensorEntityDescription(
    SensorEntityDescription,
):
    """Describes a WF Sensor."""

    value_fn: Callable[[WeatherFlowData], int | str | datetime | None]
    icon_fn: Callable[[WeatherFlowData], str] | None = None
    extra_state_attributes_fn: Callable[[WeatherFlowData], dict[str, Any]] | None = None


def wind_direction_icon_fn(degree: int) -> str:
    """Return a wind icon based on the degrees."""
    degree = degree % 360  # Normalize degrees
    direction_ranges = {
        range(23): "mdi:arrow-up-thin",
        range(23, 68): "mdi:arrow-top-right-thin",
        range(68, 113): "mdi:arrow-right-thin",
        range(113, 158): "mdi:arrow-bottom-right-thin",
        range(158, 203): "mdi:arrow-down-thin",
        range(203, 248): "mdi:arrow-bottom-left-thin",
        range(248, 293): "mdi:arrow-left-thin",
        range(293, 338): "mdi:arrow-top-left-thin",
        range(338, 361): "mdi:arrow-up-thin",
    }

    for degree_range, icon in direction_ranges.items():
        if degree in degree_range:
            return icon

    return "mdi:compass-outline"


WF_SENSORS: tuple[WeatherFlowCloudSensorEntityDescription, ...] = (
    WeatherFlowCloudSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        value_fn=lambda data: data.observation.obs[0].air_density,
        native_unit_of_measurement="kg/m³",
    ),
    # Temp Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].air_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        value_fn=lambda data: data.observation.obs[0].dew_point,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="feels_like",
        translation_key="feels_like",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].feels_like,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].heat_index,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_chill",
        translation_key="wind_chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].wind_chill,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].wet_bulb_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_globe_temperature",
        translation_key="wet_bulb_globe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.observation.obs[0].wet_bulb_globe_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_state_attributes_fn=lambda data: {
            "flag": data.observation.obs[0].wet_bulb_globe_temperature_flag.name,
            "category": data.observation.obs[0].wet_bulb_globe_temperature_category,
        },
    ),
    # Pressure Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="barometric_pressure",
        translation_key="barometric_pressure",
        value_fn=lambda data: data.observation.obs[0].barometric_pressure,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="sea_level_pressure",
        translation_key="sea_level_pressure",
        value_fn=lambda data: data.observation.obs[0].sea_level_pressure,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="station_pressure",
        translation_key="station_pressure",
        value_fn=lambda data: data.observation.obs[0].station_pressure,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    # Wind Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.observation.obs[0].wind_direction,
        extra_state_attributes_fn=lambda data: {
            "cardinal": str(data.observation.obs[0].wind_cardinal_direction),
        },
        icon_fn=lambda data: wind_direction_icon_fn(
            data.observation.obs[0].wind_direction
        ),
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_direction_cardinal",
        translation_key="wind_direction_cardinal",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ],
        value_fn=lambda data: str(data.observation.obs[0].wind_cardinal_direction),
        icon_fn=lambda data: wind_direction_icon_fn(  # The wind direction icon function is more precise so lets use it again here
            data.observation.obs[0].wind_direction
        ),
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_avg",
        translation_key="wind_avg",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.observation.obs[0].wind_avg,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.observation.obs[0].wind_gust,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.observation.obs[0].wind_lull,
    ),
    # Lightning Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_strike_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.observation.obs[0].lightning_strike_count,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count_last_1hr",
        translation_key="lightning_strike_count_last_1hr",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.observation.obs[0].lightning_strike_count_last_1hr,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count_last_3hr",
        translation_key="lightning_strike_count_last_3hr",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.observation.obs[0].lightning_strike_count_last_3hr,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_distance",
        translation_key="lightning_strike_last_distance",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda data: data.observation.obs[0].lightning_strike_last_distance,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_epoch",
        translation_key="lightning_strike_last_epoch",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: datetime.fromtimestamp(
            data.observation.obs[0].lightning_strike_last_epoch, tz=UTC
        ),
    ),
)


#
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeatherFlow sensors based on a config entry."""

    coordinator: WeatherFlowCloudDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    stations = coordinator.data.keys()

    for sensor_description in WF_SENSORS:
        for station_id in stations:
            async_add_entities(
                [
                    WeatherFlowCloudSensor(
                        coordinator=coordinator,
                        description=sensor_description,
                        station_id=station_id,
                    )
                ],
                update_before_add=True,
            )


class WeatherFlowCloudSensor(WeatherFlowCloudEntity, SensorEntity):
    """Implementation of a WeatherFlow sensor."""

    entity_description: WeatherFlowCloudSensorEntityDescription

    @property
    def native_value(self) -> StateType | date | datetime | Decimal | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.station_id])

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.coordinator.data[self.station_id]
            )
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(
                self.coordinator.data[self.station_id]
            )
        return super().icon
