"""Support for Sofar binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.enums import PowerControlFlags
from sofar_modbus.modern.faults import FaultCategory

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 0

_DISABLED_BY_DEFAULT = frozenset(
    {
        FaultCategory.ARC_FAULT,
        FaultCategory.COMBINER_BOX,
        FaultCategory.INPUT_FUSE,
        FaultCategory.STRING_FUSE,
    }
)


@dataclass(frozen=True, kw_only=True)
class SofarBinarySensorEntityDescription(
    SofarEntityDescription, BinarySensorEntityDescription
):
    """Describe a Sofar binary sensor."""

    is_on_fn: Callable[[SofarInverter], bool | None]


def _fault_sensor(category: FaultCategory) -> SofarBinarySensorEntityDescription:
    """Describe the problem sensor for one fault category."""
    return SofarBinarySensorEntityDescription(
        key=f"fault_{category.value}",
        component="state",
        translation_key=f"fault_{category.value}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=category not in _DISABLED_BY_DEFAULT,
        is_on_fn=lambda device: any(
            fault.category is category for fault in device.state.active_faults
        ),
    )


BINARY_SENSOR_DESCRIPTIONS: tuple[SofarBinarySensorEntityDescription, ...] = (
    *(_fault_sensor(category) for category in FaultCategory),
    SofarBinarySensorEntityDescription(
        key="active_power_limit_enabled",
        component="active_power_control",
        translation_key="active_power_limit_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda device: (
            None
            if (flags := device.active_power_control.power_control) is None
            else PowerControlFlags.ACTIVE_POWER in flags
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar binary sensor platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components
    async_add_entities(
        SofarBinarySensor(runtime_data, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.component in served
    )


class SofarBinarySensor(SofarEntity, BinarySensorEntity):
    """Defines a Sofar binary sensor."""

    entity_description: SofarBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.device)
