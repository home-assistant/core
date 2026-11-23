"""Support for Sofar binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntFlag
from typing import override

from sofar_modbus import FaultCategory, PowerControlFlags, SofarInverter

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription, async_remove_unserved_entities

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

    flags_fn: Callable[[SofarInverter], IntFlag | None]
    flag: IntFlag


FLAG_SENSOR_DESCRIPTIONS: tuple[SofarFlagBinarySensorDescription, ...] = (
    SofarFlagBinarySensorDescription(
        key="active_power_limit_enabled",
        component="active_power_control",
        translation_key="active_power_limit_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        flags_fn=lambda device: device.active_power_control.power_control,
        flag=PowerControlFlags.ACTIVE_POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar binary sensor platform."""
    async_remove_unserved_entities(
        hass,
        entry,
        Platform.BINARY_SENSOR,
        FAULT_SENSOR_DESCRIPTIONS + FLAG_SENSOR_DESCRIPTIONS,
    )
    runtime_data = entry.runtime_data
    entities: list[SofarFaultBinarySensor | SofarFlagBinarySensor] = [
        SofarFaultBinarySensor(runtime_data, description)
        for description in FAULT_SENSOR_DESCRIPTIONS
        if description.component in runtime_data.served_components
    ]
    entities.extend(
        SofarFlagBinarySensor(runtime_data, description)
        for description in FLAG_SENSOR_DESCRIPTIONS
        if description.component in runtime_data.served_components
    )
    async_add_entities(entities)


class SofarFaultBinarySensor(SofarEntity, BinarySensorEntity):
    """Reports whether any fault in one subsystem is currently active."""

    entity_description: SofarFaultBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool:
        return any(
            fault.category is self.entity_description.category
            for fault in self.coordinator.device.state.active_faults
        )


class SofarFlagBinarySensor(SofarEntity, BinarySensorEntity):
    """Reports whether one bit of a flags register is set."""

    entity_description: SofarFlagBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        flags = self.entity_description.flags_fn(self.coordinator.device)
        return None if flags is None else self.entity_description.flag in flags
