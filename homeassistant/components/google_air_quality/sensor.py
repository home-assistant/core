"""Creates the sensor entities for Google Air Quality."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from google_air_quality_api.model import AirQualityData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
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


@callback
def _get_local_aqi_extra_state_attributes(
    data: AirQualityData,
) -> dict[str, int] | None:
    """Return the name of the current work area."""
    if data.indexes[1].aqi:
        return {
            data.indexes[1].display_name: data.indexes[1].aqi,
        }
    return None


@dataclass(frozen=True, kw_only=True)
class AirQualitySensorEntityDescription(SensorEntityDescription):
    """Describes Air Quality sensor entity."""

    exists_fn: Callable[[Any], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[Any], Mapping[str, Any] | None] = (
        lambda _: None
    )
    translation_key_fn: Callable[[Any], str]
    option_fn: Callable[[Any], list[str] | None] = lambda _: None
    value_fn: Callable[[Any], StateType | datetime]


AIR_QUALITY_SENSOR_TYPES: tuple[AirQualitySensorEntityDescription, ...] = (
    AirQualitySensorEntityDescription(
        key="uaqi",
        translation_key_fn=lambda x: "uaqi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: x.indexes[0].aqi,
        extra_state_attributes_fn=_get_local_aqi_extra_state_attributes,
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_category",
        translation_key_fn=lambda x: "uaqi_category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[0].category,
    ),
    AirQualitySensorEntityDescription(
        key="local_category",
        translation_key_fn=lambda x: "local_category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[1].category,
    ),
    AirQualitySensorEntityDescription(
        key="pm10",
        translation_key_fn=lambda x: "pm10",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm10.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="pm25",
        translation_key_fn=lambda x: "pm25",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm25.concentration.value,
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

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self.entity_description.extra_state_attributes_fn(self.coordinator.data)

    @property
    def translation_key(self) -> str:
        """Return the state attributes."""
        return self.entity_description.translation_key_fn(self.coordinator.data)
