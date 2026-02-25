"""Sensor platform for SystemNexa2 integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemNexa2ConfigEntry, SystemNexa2DataUpdateCoordinator
from .entity import SystemNexa2Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemNexa2SensorEntityDescription(SensorEntityDescription):
    """Describes SystemNexa2 sensor entity."""

    value_fn: Callable[[SystemNexa2DataUpdateCoordinator], str | int | None]


SENSOR_DESCRIPTIONS: tuple[SystemNexa2SensorEntityDescription, ...] = (
    SystemNexa2SensorEntityDescription(
        key="wifi_dbm",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.info_data.wifi_dbm,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemNexa2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SystemNexa2Sensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.value_fn(coordinator) is not None
    )


class SystemNexa2Sensor(SystemNexa2Entity, SensorEntity):
    """Representation of a SystemNexa2 sensor."""

    entity_description: SystemNexa2SensorEntityDescription

    def __init__(
        self,
        coordinator: SystemNexa2DataUpdateCoordinator,
        entity_description: SystemNexa2SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            key=entity_description.key,
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
