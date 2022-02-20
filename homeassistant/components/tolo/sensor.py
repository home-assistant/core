"""TOLO Sauna (non-binary, general) sensors."""
from collections.abc import Callable
from dataclasses import dataclass

from tololib.message_info import StatusInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


@dataclass
class ToloSensorEntityDescriptionBase:
    """Required values when describing TOLO Sensor entities."""

    getter: Callable[[StatusInfo], int]


@dataclass
class ToloSensorEntityDescription(
    SensorEntityDescription, ToloSensorEntityDescriptionBase
):
    """Class describing TOLO Sensor entities."""


SENSORS = (
    ToloSensorEntityDescription(
        key="water_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:waves-arrow-up",
        name="Water Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        getter=lambda s: s.water_level_percent,
    ),
    ToloSensorEntityDescription(
        key="tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Tank Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        getter=lambda s: s.tank_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up (non-binary, general) sensors for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ToloSensorEntity(coordinator, entry, description) for description in SENSORS
    )


class ToloSensorEntity(ToloSaunaCoordinatorEntity, SensorEntity):
    """TOLO Number entity."""

    entity_description: ToloSensorEntityDescription

    def __init__(
        self,
        coordinator: ToloSaunaUpdateCoordinator,
        entry: ConfigEntry,
        entity_description: ToloSensorEntityDescription,
    ) -> None:
        """Initialize TOLO Number entity."""
        super().__init__(coordinator, entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    def native_value(self) -> int:
        """Return native value of the TOLO sensor."""
        return self.entity_description.getter(self.coordinator.data.status)
