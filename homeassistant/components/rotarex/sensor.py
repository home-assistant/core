"""Sensor platform for the Rotarex integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from rotarex_dimes_srg_api import RotarexSyncData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RotarexConfigEntry
from .const import DOMAIN
from .coordinator import RotarexDataUpdateCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class RotarexTankSensorEntityDescription(SensorEntityDescription):
    """Entity description for Rotarex tank sensors."""

    value_fn: Callable[[RotarexSyncData], float | None]


SENSOR_DESCRIPTIONS: tuple[RotarexTankSensorEntityDescription, ...] = (
    RotarexTankSensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync.level,
    ),
    RotarexTankSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda sync: sync.battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RotarexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Rotarex sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        RotarexTankSensor(coordinator, tank_id, description)
        for tank_id in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    )


class RotarexTankSensor(CoordinatorEntity[RotarexDataUpdateCoordinator], SensorEntity):
    """Representation of a Rotarex tank sensor."""

    entity_description: RotarexTankSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RotarexDataUpdateCoordinator,
        tank_id: str,
        description: RotarexTankSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tank_id = tank_id
        self._attr_unique_id = f"{tank_id}_{description.key}"

        tank = coordinator.data[tank_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tank_id)},
            name=tank.name or f"Tank {tank_id}",
            manufacturer="Rotarex",
            model="DIMES SRG",
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the tank is still reported and has synchronized data."""
        tank = self.coordinator.data.get(self._tank_id)
        return super().available and tank is not None and tank.latest_sync is not None

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        latest_sync = self.coordinator.data[self._tank_id].latest_sync
        if TYPE_CHECKING:
            assert latest_sync is not None
        return self.entity_description.value_fn(latest_sync)
