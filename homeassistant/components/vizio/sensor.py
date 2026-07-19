"""Sensor platform for Vizio SmartCast devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

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

from .const import DOMAIN
from .coordinator import VizioConfigEntry, VizioDeviceCoordinator, VizioDeviceData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VizioSensorEntityDescription(SensorEntityDescription):
    """Describes a Vizio sensor entity."""

    value_fn: Callable[[VizioDeviceData], int | str | None]


SENSORS: tuple[VizioSensorEntityDescription, ...] = (
    VizioSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_level,
    ),
    VizioSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=["not_charging", "charging", "fully_charged"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.charging_status.name.lower()
            if data.charging_status is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vizio sensor entities."""
    coordinator = config_entry.runtime_data.device_coordinator
    if not coordinator.device.profile.has_battery:
        return

    async_add_entities(
        VizioSensor(config_entry, coordinator, description) for description in SENSORS
    )


class VizioSensor(CoordinatorEntity[VizioDeviceCoordinator], SensorEntity):
    """Sensor entity for battery-powered Vizio SmartCast devices."""

    _attr_has_entity_name = True
    entity_description: VizioSensorEntityDescription

    def __init__(
        self,
        config_entry: VizioConfigEntry,
        coordinator: VizioDeviceCoordinator,
        description: VizioSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        unique_id = config_entry.unique_id
        # Guard against config entries missing unique_id, which should never happen
        if TYPE_CHECKING:
            assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    @override
    def native_value(self) -> int | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
