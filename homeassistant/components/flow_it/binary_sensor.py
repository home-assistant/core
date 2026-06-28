"""Binary sensor platform for Flow-it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from flow_it_api.models import MachineStatusResponse

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlowItConfigEntry
from .entity import FlowItVmcEntity


@dataclass(frozen=True, kw_only=True)
class FlowItVmcBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Flow-it binary sensor entity."""

    value_fn: Callable[[MachineStatusResponse], bool | None]


BINARY_SENSORS: tuple[FlowItVmcBinarySensorEntityDescription, ...] = (
    FlowItVmcBinarySensorEntityDescription(
        key="ice",
        name="Ice Alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.data.alert.ice,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="condensation",
        name="Condensation Alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.data.alert.condensation,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="warmup",
        name="Warmup Mode",
        value_fn=lambda data: data.data.alert.warmup,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="service",
        name="Service Required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.data.alert.service,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="worries",
        name="General Issue",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.data.alert.worries,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="bypass_on",
        name="Bypass Active",
        value_fn=lambda data: data.data.mode.bypassOn,
    ),
    FlowItVmcBinarySensorEntityDescription(
        key="update_reboot",
        name="Update Reboot Pending",
        value_fn=lambda data: data.data.alert.update_reboot,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it binary sensors."""
    data = config_entry.runtime_data
    coordinator = data.coordinator
    vmc = data.vmc

    async_add_entities(
        FlowItVmcBinarySensor(coordinator, vmc, description)
        for description in BINARY_SENSORS
    )


class FlowItVmcBinarySensor(FlowItVmcEntity, BinarySensorEntity):
    """Flow-it binary sensor entity."""

    entity_description: FlowItVmcBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: Any,
        vmc: Any,
        description: FlowItVmcBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, vmc)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.name}_{description.key}"

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
