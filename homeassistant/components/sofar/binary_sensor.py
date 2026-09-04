"""Support for Sofar binary sensors."""

from dataclasses import dataclass
from enum import IntFlag
from typing import override

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
class SofarFaultBinarySensorDescription(
    SofarEntityDescription, BinarySensorEntityDescription
):
    """Describe a Sofar fault-category binary sensor."""

    category: FaultCategory


FAULT_SENSOR_DESCRIPTIONS: tuple[SofarFaultBinarySensorDescription, ...] = tuple(
    SofarFaultBinarySensorDescription(
        key=f"fault_{category.value}",
        component="state",
        translation_key=f"fault_{category.value}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=category not in _DISABLED_BY_DEFAULT,
        category=category,
    )
    for category in FaultCategory
)


@dataclass(frozen=True, kw_only=True)
class SofarFlagBinarySensorDescription(
    SofarEntityDescription, BinarySensorEntityDescription
):
    """Describe a Sofar binary sensor backed by one flags-register bit."""

    attribute: str
    flag: IntFlag


FLAG_SENSOR_DESCRIPTIONS: tuple[SofarFlagBinarySensorDescription, ...] = (
    SofarFlagBinarySensorDescription(
        key="active_power_limit_enabled",
        component="active_power_control",
        translation_key="active_power_limit_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        attribute="power_control",
        flag=PowerControlFlags.ACTIVE_POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus binary sensor platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components
    async_add_entities(
        SofarFaultBinarySensor(runtime_data, description)
        for description in FAULT_SENSOR_DESCRIPTIONS
        if description.component in served
    )
    async_add_entities(
        SofarFlagBinarySensor(runtime_data, description)
        for description in FLAG_SENSOR_DESCRIPTIONS
        if description.component in served
    )


class SofarFaultBinarySensor(SofarEntity, BinarySensorEntity):
    """Reports whether any fault in one subsystem is currently active."""

    entity_description: SofarFaultBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool:
        component = getattr(self.coordinator.device, self.entity_description.component)
        return any(
            fault.category is self.entity_description.category
            for fault in component.active_faults
        )


class SofarFlagBinarySensor(SofarEntity, BinarySensorEntity):
    """Reports whether one bit of a flags register is set."""

    entity_description: SofarFlagBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool:
        component = getattr(self.coordinator.device, self.entity_description.component)
        flags = getattr(component, self.entity_description.attribute)
        return self.entity_description.flag in flags
