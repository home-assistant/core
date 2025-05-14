"""Creates the sensor entities for the mower."""

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GooglePhotosConfigEntry
from .const import DOMAIN
from .coordinator import GooglePhotosUpdateCoordinator

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
class AutomowerSensorEntityDescription(SensorEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[Any], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[Any], Mapping[str, Any] | None] = (
        lambda _: None
    )
    option_fn: Callable[[Any], list[str] | None] = lambda _: None
    value_fn: Callable[[Any], StateType | datetime]


MOWER_SENSOR_TYPES: tuple[AutomowerSensorEntityDescription, ...] = (
    AutomowerSensorEntityDescription(
        key="uaqi",
        translation_key="uaqi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: x.indexes[0].aqi,
        extra_state_attributes_fn=_get_local_aqi_extra_state_attributes,
    ),
    AutomowerSensorEntityDescription(
        key="category",
        translation_key="category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.indexes[0].category,
        extra_state_attributes_fn=lambda x: {
            x.indexes[1].display_name: x.indexes[1].category,
        },
    ),
    AutomowerSensorEntityDescription(
        key="pm10",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm10.concentration.value,
    ),
    AutomowerSensorEntityDescription(
        key="pm25",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x.pollutants.pm25.concentration.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    entities.extend(
        AutomowerSensorEntity(coordinator, description)
        for description in MOWER_SENSOR_TYPES
    )
    async_add_entities(entities)


class AutomowerSensorEntity(
    CoordinatorEntity[GooglePhotosUpdateCoordinator], SensorEntity
):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerSensorEntityDescription
    config_entry: GooglePhotosConfigEntry
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GooglePhotosUpdateCoordinator,
        description: AutomowerSensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(coordinator)
        self.entity_description = description
        name = f"{self.coordinator.config_entry.data[CONF_LATITUDE]}_{self.coordinator.config_entry.data[CONF_LONGITUDE]}"
        self._attr_unique_id = f"{description.key}_{name}"
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            name=name,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    # @property
    # def options(self) -> list[str] | None:
    #     """Return the option of the sensor."""
    #     return self.entity_description.option_fn(self.mower_attributes)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self.entity_description.extra_state_attributes_fn(self.coordinator.data)
