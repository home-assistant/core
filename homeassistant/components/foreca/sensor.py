"""Sensor platform for the Foreca integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfVolumetricFlux
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator, ForecaWeatherData
from .entity import ForecaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ForecaSensorEntityDescription(SensorEntityDescription):
    """Describes a Foreca sensor entity."""

    value_fn: Callable[[ForecaWeatherData], StateType]


SENSOR_TYPES: tuple[ForecaSensorEntityDescription, ...] = (
    ForecaSensorEntityDescription(
        key="precipitation_intensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.current.precip_rate,
    ),
    ForecaSensorEntityDescription(
        key="thunderstorm_probability",
        translation_key="thunderstorm_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current.thunder_prob,
    ),
    ForecaSensorEntityDescription(
        key="precipitation_probability",
        translation_key="precipitation_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current.precip_prob,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Foreca sensors for every configured location."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            (
                ForecaSensor(coordinator, subentry_id, description)
                for description in SENSOR_TYPES
            ),
            config_subentry_id=subentry_id,
        )


class ForecaSensor(ForecaEntity, SensorEntity):
    """Define a Foreca sensor."""

    entity_description: ForecaSensorEntityDescription

    def __init__(
        self,
        coordinator: ForecaUpdateCoordinator,
        subentry_id: str,
        description: ForecaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{subentry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
