"""Creates the sensor entities for Google Air Quality."""

from collections.abc import Callable
from dataclasses import dataclass
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
    CONCENTRATION_PARTS_PER_MILLION,
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
    options_fn: Callable[[AirQualityData], list[str] | None] = lambda _: None
    value_fn: Callable[[AirQualityData], StateType]


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
        options_fn=lambda x: x.indexes[0].category_options,
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
        options_fn=lambda x: x.indexes[1].category_options,
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_dominant_pollutant",
        translation_key="uaqi_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[0].dominant_pollutant,
        options_fn=lambda x: x.indexes[0].pollutant_options,
    ),
    AirQualitySensorEntityDescription(
        key="local_dominant_pollutant",
        translation_key="local_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[1].dominant_pollutant,
        options_fn=lambda x: x.indexes[1].pollutant_options,
    ),
    AirQualitySensorEntityDescription(
        key="co",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda x: x.pollutants.co.concentration.value / 1000,
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

    for subentry_id, subenrty in entry.subentries.items():
        async_add_entities(
            [
                AirQualitySensorEntity(coordinator, description, subentry_id, subenrty)
                for description in AIR_QUALITY_SENSOR_TYPES
                if description.exists_fn(coordinator.data[subentry_id])
            ],
            config_subentry_id=subentry_id,
        )


class AirQualitySensorEntity(
    CoordinatorEntity[GoogleAirQualityUpdateCoordinator], SensorEntity
):
    """Defining the Air Quality Sensors with AirQualitySensorEntityDescription."""

    entity_description: AirQualitySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleAirQualityUpdateCoordinator,
        description: AirQualitySensorEntityDescription,
        subentry_id: str,
        subentry,
    ) -> None:
        """Set up Air Quality Sensors."""
        super().__init__(coordinator)
        self.entity_description = description
        name = f"{subentry.data[CONF_LATITUDE]}_{subentry.data[CONF_LONGITUDE]}"
        self._attr_unique_id = f"{description.key}_{name}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.config_entry.entry_id}_{subentry_id}")
            },
            name=name,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_translation_placeholders = {
            "local_aqi": coordinator.data[subentry_id].indexes[1].display_name
        }
        self.subentry_id = subentry_id

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.subentry_id])

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options_fn(
            self.coordinator.data[self.subentry_id]
        )
