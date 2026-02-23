"""Sensor platform for Zinvolt integration."""

from collections.abc import Callable
from dataclasses import dataclass

from zinvolt.models import BatteryState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator


@dataclass(kw_only=True, frozen=True)
class ZinvoltBatteryStateDescription(SensorEntityDescription):
    """Sensor description for Zinvolt battery state."""

    value_fn: Callable[[BatteryState], float]


SENSORS: tuple[ZinvoltBatteryStateDescription, ...] = (
    ZinvoltBatteryStateDescription(
        key="state_of_charge",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.current_power.state_of_charge,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZinvoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    async_add_entities(
        ZinvoltBatteryStateSensor(coordinator, description)
        for description in SENSORS
        for coordinator in entry.runtime_data.values()
    )


class ZinvoltBatteryStateSensor(
    CoordinatorEntity[ZinvoltDeviceCoordinator], SensorEntity
):
    """Zinvolt battery state sensor."""

    _attr_has_entity_name = True
    entity_description: ZinvoltBatteryStateDescription

    def __init__(
        self,
        coordinator: ZinvoltDeviceCoordinator,
        description: ZinvoltBatteryStateDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}.{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="Zinvolt",
            name=coordinator.data.name,
            serial_number=coordinator.data.serial_number,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
