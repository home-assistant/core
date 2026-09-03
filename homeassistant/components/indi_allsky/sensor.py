"""Support for INDI Allsky sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    IndiAllSkyConfigEntry,
    IndiAllSkyData,
    IndiAllSkyDataUpdateCoordinator,
)
from .entity import IndiAllSkyEntity

PARALLEL_UPDATES = 0


_UNSUPPORTED_TEMPERATURE = -273.15


@dataclass(frozen=True, kw_only=True)
class IndiAllSkySensorEntityDescription(SensorEntityDescription):
    """Class describing INDI Allsky sensor entities."""

    value_fn: Callable[[IndiAllSkyData], StateType]


SENSOR_DESCRIPTIONS: tuple[IndiAllSkySensorEntityDescription, ...] = (
    IndiAllSkySensorEntityDescription(
        key="binmode",
        translation_key="binmode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.binmode if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="exposure",
        translation_key="exposure",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.exposure.exposure if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="filename",
        translation_key="filename",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.filename if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="gain",
        translation_key="gain",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.gain if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="sqm",
        translation_key="sqm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.sqm if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="stars",
        translation_key="stars",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.stars if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.exposure.temp
            if data.exposure and data.exposure.temp != _UNSUPPORTED_TEMPERATURE
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up INDI Allsky sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        IndiAllSkySensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class IndiAllSkySensor(IndiAllSkyEntity, SensorEntity):
    """Representation of an INDI Allsky sensor."""

    entity_description: IndiAllSkySensorEntityDescription

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
        description: IndiAllSkySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
