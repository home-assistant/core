"""Dormakaba dKey integration binary sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from py_dormakaba_dkey.commands import DoorPosition, Notifications, UnlockStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DormakabaDkeyConfigEntry, DormakabaDkeyCoordinator
from .entity import DormakabaDkeyEntity


@dataclass(frozen=True, kw_only=True)
class DormakabaDkeyBinarySensorDescription(BinarySensorEntityDescription):
    """Describes Dormakaba dKey binary sensor entity."""

    is_on: Callable[[Notifications], bool]


BINARY_SENSOR_DESCRIPTIONS = (
    DormakabaDkeyBinarySensorDescription(
        key="door_position",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on=lambda state: state.door_position == DoorPosition.OPEN,
    ),
    DormakabaDkeyBinarySensorDescription(
        key="security_locked",
        translation_key="deadbolt",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on=lambda state: state.unlock_status
        not in (UnlockStatus.SECURITY_LOCKED, UnlockStatus.UNLOCKED_SECURITY_LOCKED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DormakabaDkeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform for Dormakaba dKey."""
    coordinator = entry.runtime_data
    async_add_entities(
        DormakabaDkeyBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class DormakabaDkeyBinarySensor(DormakabaDkeyEntity, BinarySensorEntity):
    """Dormakaba dKey binary sensor."""

    _attr_has_entity_name = True
    entity_description: DormakabaDkeyBinarySensorDescription

    def __init__(
        self,
        coordinator: DormakabaDkeyCoordinator,
        description: DormakabaDkeyBinarySensorDescription,
    ) -> None:
        """Initialize a Dormakaba dKey binary sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.lock.address}_{description.key}"
        super().__init__(coordinator)

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_on = self.entity_description.is_on(self.coordinator.lock.state)
