"""Binary sensor platform for Atomberg water purifier faults."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DEVICE_TYPE_WATER_PURIFIER, AtombergDevice
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AtombergBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a purifier fault binary sensor."""

    faults_key: str
    is_on_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[AtombergBinarySensorDescription, ...] = (
    AtombergBinarySensorDescription(
        key="filter_choked",
        translation_key="filter_choked",
        device_class=BinarySensorDeviceClass.PROBLEM,
        faults_key="choking_faults",
        is_on_fn=lambda faults: bool(faults.get("filter_choke")),
    ),
    AtombergBinarySensorDescription(
        key="valve_fault",
        translation_key="valve_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        faults_key="choking_faults",
        is_on_fn=lambda faults: bool(faults.get("sv_fault")),
    ),
    AtombergBinarySensorDescription(
        key="system_fault",
        translation_key="system_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        faults_key="system_faults",
        is_on_fn=lambda faults: not faults.get("healthy", True),
    ),
    AtombergBinarySensorDescription(
        key="no_water",
        translation_key="no_water",
        faults_key="system_faults",
        is_on_fn=lambda faults: "NO_WATER" in faults.get("codes", []),
    ),
    AtombergBinarySensorDescription(
        key="tank_full",
        translation_key="tank_full",
        faults_key="system_faults",
        is_on_fn=lambda faults: "TANK_FULL" in faults.get("codes", []),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergBinarySensor(coordinator, device, description)
        for device in coordinator.devices_of_type(DEVICE_TYPE_WATER_PURIFIER)
        for description in BINARY_SENSORS
        if description.faults_key in coordinator.data.get(device.device_id, {})
    )


class AtombergBinarySensor(AtombergEntity, BinarySensorEntity):
    """Water purifier fault or status binary sensor."""

    entity_description: AtombergBinarySensorDescription

    def __init__(
        self,
        coordinator: AtombergCoordinator,
        device: AtombergDevice,
        description: AtombergBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the condition is active."""
        description = self.entity_description
        return description.is_on_fn(self.device_state[description.faults_key] or {})
