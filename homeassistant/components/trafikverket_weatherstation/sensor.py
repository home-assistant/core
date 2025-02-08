"""Weather information for air and road temperature (by Trafikverket)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pytrafikverket.models import WeatherStationInfoModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import TVWeatherConfigEntry
from .const import ATTRIBUTION, CONF_STATION, DOMAIN
from .coordinator import TVDataUpdateCoordinator

PRECIPITATION_TYPE = [
    "no",
    "rain",
    "freezing_rain",
    "snow",
    "sleet",
    "yes",
]

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TrafikverketSensorEntityDescription(SensorEntityDescription):
    """Describes Trafikverket sensor entity."""

    value_fn: Callable[[WeatherStationInfoModel], StateType | datetime]


def add_utc_timezone(date_time: datetime | None) -> datetime | None:
    """Add UTC timezone if datetime."""
    if date_time:
        return date_time.replace(tzinfo=dt_util.UTC)
    return None


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="air_temp",
        translation_key="air_temperature",
        value_fn=lambda data: data.air_temp,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="road_temp",
        translation_key="road_temperature",
        value_fn=lambda data: data.road_temp,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation",
        translation_key="precipitation",
        value_fn=lambda data: data.precipitationtype,
        entity_registry_enabled_default=False,
        options=PRECIPITATION_TYPE,
        device_class=SensorDeviceClass.ENUM,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        value_fn=lambda data: data.winddirection,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed",
        value_fn=lambda data: data.windforce,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed_max",
        translation_key="wind_speed_max",
        value_fn=lambda data: data.windforcemax,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="humidity",
        value_fn=lambda data: data.humidity,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation_amount",
        value_fn=lambda data: data.precipitation_amount,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="measure_time",
        translation_key="measure_time",
        value_fn=lambda data: data.measure_time,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TrafikverketSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        value_fn=lambda data: data.dew_point,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="visible_distance",
        translation_key="visible_distance",
        value_fn=lambda data: data.visible_distance,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="road_ice_depth",
        translation_key="road_ice_depth",
        value_fn=lambda data: data.road_ice_depth,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="road_snow_depth",
        translation_key="road_snow_depth",
        value_fn=lambda data: data.road_snow_depth,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="road_water_depth",
        translation_key="road_water_depth",
        value_fn=lambda data: data.road_water_depth,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="road_water_equivalent_depth",
        translation_key="road_water_equivalent_depth",
        value_fn=lambda data: data.road_water_equivalent_depth,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_height",
        translation_key="wind_height",
        value_fn=lambda data: data.wind_height,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="modified_time",
        translation_key="modified_time",
        value_fn=lambda data: add_utc_timezone(data.modified_time),
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TVWeatherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        TrafikverketWeatherStation(
            coordinator, entry.entry_id, entry.data[CONF_STATION], description
        )
        for description in SENSOR_TYPES
    )


class TrafikverketWeatherStation(
    CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity
):
    """Representation of a Trafikverket sensor."""

    entity_description: TrafikverketSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
        sensor_station: str,
        description: TrafikverketSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v2.0",
            name=sensor_station,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return state of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
