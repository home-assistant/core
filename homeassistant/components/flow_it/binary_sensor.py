"""Binary sensor platform for Flow-it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flow_it_api.models import MachineStatusResponse

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlowItConfigEntry
from .entity import FlowItVmcEntity


@dataclass(frozen=True, kw_only=True)
class FlowItVmcBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Flow-it binary sensor entity."""

    value_fn: Callable[[MachineStatusResponse], bool | None]


BINARY_SENSORS: tuple[FlowItVmcBinarySensorEntityDescription, ...] = (
    FlowItVmcBinarySensorEntityDescription(
        key="bypass_on",
        translation_key="bypass_on",
        value_fn=lambda data: data.data.mode.bypassOn,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="condensation",
        translation_key="condensation",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.condensation,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="ice",
        translation_key="ice",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.ice,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="service",
        translation_key="service",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.service,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="update_reboot",
        translation_key="update_reboot",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.update_reboot,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="warmup",
        translation_key="warmup",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.data.alert.warmup,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="worries",
        translation_key="worries",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.worries,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it binary sensors."""
    data = config_entry.runtime_data
    async_add_entities(
        FlowItVmcBinarySensor(data.coordinator, data.vmc, description)
        for description in BINARY_SENSORS
    )


class FlowItVmcBinarySensor(FlowItVmcEntity, BinarySensorEntity):
    """Flow-it binary sensor entity."""

    entity_description: FlowItVmcBinarySensorEntityDescription

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data.state)
