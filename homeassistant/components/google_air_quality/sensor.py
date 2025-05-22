"""Creates the sensor entities for Google Air Quality."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from google_air_quality_api.model import AirQualityData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleAirQualityConfigEntry
from .const import DOMAIN
from .coordinator import GoogleAirQualityUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirQualitySensorEntityDescription(SensorEntityDescription):
    """Describes Air Quality sensor entity."""

    exists_fn: Callable[[AirQualityData], bool] = lambda _: True
    value_fn: Callable[[AirQualityData], StateType | datetime]


AIR_QUALITY_SENSOR_TYPES: tuple[AirQualitySensorEntityDescription, ...] = (
    AirQualitySensorEntityDescription(
        key="uaqi",
        translation_key="uaqi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: x.indexes[0].aqi,
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_category",
        translation_key="uaqi_category",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "excellent_air_quality",
            "good_air_quality",
            "low_air_quality",
            "moderate_air_quality",
            "poor_air_quality",
        ],
        value_fn=lambda x: x.indexes[0].category,
    ),
    AirQualitySensorEntityDescription(
        key="local_aqi",
        translation_key="local_aqi",
        exists_fn=lambda x: x.indexes[1].aqi is not None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: x.indexes[1].aqi,
    ),
    AirQualitySensorEntityDescription(
        key="local_category",
        translation_key="local_category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[1].category,
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_dominant_pollutant",
        translation_key="uaqi_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[0].dominant_pollutant,
    ),
    AirQualitySensorEntityDescription(
        key="local_dominant_pollutant",
        translation_key="local_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[1].dominant_pollutant,
    ),
    AirQualitySensorEntityDescription(
        key="co",
        translation_key="carbon_monoxide",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        value_fn=lambda x: x.pollutants.co.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="no2",
        translation_key="nitrogen_dioxide",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        value_fn=lambda x: x.pollutants.no2.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="o3",
        translation_key="ozone",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        value_fn=lambda x: x.pollutants.o3.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="pm10",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm10.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="pm25",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm25.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="so2",
        translation_key="sulphur_dioxide",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        value_fn=lambda x: x.pollutants.so2.concentration.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleAirQualityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    entities.extend(
        AirQualitySensorEntity(coordinator, description)
        for description in AIR_QUALITY_SENSOR_TYPES
        if description.exists_fn(coordinator.data)
    )
    async_add_entities(entities)


class AirQualitySensorEntity(
    CoordinatorEntity[GoogleAirQualityUpdateCoordinator], SensorEntity
):
    """Defining the Air Quality Sensors with AirQualitySensorEntityDescription."""

    entity_description: AirQualitySensorEntityDescription
    config_entry: GoogleAirQualityConfigEntry
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleAirQualityUpdateCoordinator,
        description: AirQualitySensorEntityDescription,
    ) -> None:
        """Set up Air Quality Sensors."""
        super().__init__(coordinator)
        self.entity_description = description
        name = f"{self.coordinator.config_entry.data[CONF_LATITUDE]}_{self.coordinator.config_entry.data[CONF_LONGITUDE]}"
        self._attr_unique_id = f"{description.key}_{name}"
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            name=name,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_translation_placeholders = {
            "local_aqi": coordinator.data.indexes[1].display_name
        }

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
