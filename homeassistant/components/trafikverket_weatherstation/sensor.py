"""Weather information for air and road temperature (by Trafikverket)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_utc

from .const import ATTRIBUTION, CONF_STATION, DOMAIN, NONE_IS_ZERO_SENSORS
from .coordinator import TVDataUpdateCoordinator

WIND_DIRECTIONS = [
    "east",
    "north_east",
    "east_south_east",
    "north",
    "north_north_east",
    "north_north_west",
    "north_west",
    "south",
    "south_east",
    "south_south_west",
    "south_west",
    "west",
]
PRECIPITATION_AMOUNTNAME = [
    "error",
    "mild_rain",
    "moderate_rain",
    "heavy_rain",
    "mild_snow_rain",
    "moderate_snow_rain",
    "heavy_snow_rain",
    "mild_snow",
    "moderate_snow",
    "heavy_snow",
    "other",
    "none",
    "error",
]
PRECIPITATION_TYPE = [
    "drizzle",
    "hail",
    "none",
    "rain",
    "snow",
    "rain_snow_mixed",
    "freezing_rain",
]


@dataclass
class TrafikverketRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class TrafikverketSensorEntityDescription(
    SensorEntityDescription, TrafikverketRequiredKeysMixin
):
    """Describes Trafikverket sensor entity."""


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="air_temp",
        translation_key="air_temperature",
        api_key="air_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="road_temp",
        translation_key="road_temperature",
        api_key="road_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation",
        translation_key="precipitation",
        api_key="precipitationtype_translated",
        name="Precipitation type",
        icon="mdi:weather-snowy-rainy",
        entity_registry_enabled_default=False,
        options=PRECIPITATION_TYPE,
        device_class=SensorDeviceClass.ENUM,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        api_key="winddirection",
        name="Wind direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:flag-triangle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_direction_text",
        translation_key="wind_direction_text",
        api_key="winddirectiontext_translated",
        name="Wind direction text",
        icon="mdi:flag-triangle",
        options=WIND_DIRECTIONS,
        device_class=SensorDeviceClass.ENUM,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed",
        api_key="windforce",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed_max",
        translation_key="wind_speed_max",
        api_key="windforcemax",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        icon="mdi:weather-windy-variant",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="humidity",
        api_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation_amount",
        api_key="precipitation_amount",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation_amountname",
        translation_key="precipitation_amountname",
        api_key="precipitation_amountname_translated",
        icon="mdi:weather-pouring",
        entity_registry_enabled_default=False,
        options=PRECIPITATION_AMOUNTNAME,
        device_class=SensorDeviceClass.ENUM,
    ),
    TrafikverketSensorEntityDescription(
        key="measure_time",
        translation_key="measure_time",
        api_key="measure_time",
        icon="mdi:clock",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TrafikverketWeatherStation(
            coordinator, entry.entry_id, entry.data[CONF_STATION], description
        )
        for description in SENSOR_TYPES
    )


def _to_datetime(measuretime: str) -> datetime:
    """Return isoformatted utc time."""
    time_obj = datetime.strptime(measuretime, "%Y-%m-%dT%H:%M:%S.%f%z")
    return as_utc(time_obj)


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
        if self.entity_description.api_key == "measure_time":
            if TYPE_CHECKING:
                assert self.coordinator.data.measure_time
            return self.coordinator.data.measure_time

        state: StateType = getattr(
            self.coordinator.data, self.entity_description.api_key
        )

        # For zero value state the api reports back None for certain sensors.
        if state is None and self.entity_description.key in NONE_IS_ZERO_SENSORS:
            return 0
        return state

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if TYPE_CHECKING:
            assert self.coordinator.data.active
        return self.coordinator.data.active and super().available
