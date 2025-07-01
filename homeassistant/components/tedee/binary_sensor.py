"""Tedee sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from aiotedee import TedeeLock
from aiotedee.lock import TedeeDoorState, TedeeLockState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TedeeConfigEntry
from .entity import TedeeDescriptionEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TedeeBinarySensorEntityDescription(
    BinarySensorEntityDescription,
):
    """Describes Tedee binary sensor entity."""

    is_on_fn: Callable[[TedeeLock], bool | None]
    supported_fn: Callable[[TedeeLock], bool] = lambda _: True
    available_fn: Callable[[TedeeLock], bool] = lambda _: True


ENTITIES: tuple[TedeeBinarySensorEntityDescription, ...] = (
    TedeeBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda lock: lock.is_charging,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TedeeBinarySensorEntityDescription(
        key="semi_locked",
        translation_key="semi_locked",
        is_on_fn=lambda lock: lock.state is TedeeLockState.HALF_OPEN,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TedeeBinarySensorEntityDescription(
        key="pullspring_enabled",
        translation_key="pullspring_enabled",
        is_on_fn=lambda lock: lock.is_enabled_pullspring,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TedeeBinarySensorEntityDescription(
        key="uncalibrated",
        translation_key="uncalibrated",
        is_on_fn=(
            lambda lock: lock.state is TedeeLockState.UNCALIBRATED
            or lock.state is TedeeLockState.UNKNOWN
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TedeeBinarySensorEntityDescription(
        key="door_state",
        is_on_fn=lambda lock: lock.door_state is TedeeDoorState.OPENED,
        device_class=BinarySensorDeviceClass.DOOR,
        supported_fn=lambda lock: lock.door_state is not TedeeDoorState.NOT_PAIRED,
        available_fn=lambda lock: lock.door_state
        not in [TedeeDoorState.UNCALIBRATED, TedeeDoorState.DISCONNECTED],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TedeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tedee sensor entity."""
    coordinator = entry.runtime_data

    def _async_add_new_lock(locks: list[TedeeLock]) -> None:
        async_add_entities(
            TedeeBinarySensorEntity(lock, coordinator, entity_description)
            for entity_description in ENTITIES
            for lock in locks
            if entity_description.supported_fn(lock)
        )

    coordinator.new_lock_callbacks.append(_async_add_new_lock)
    _async_add_new_lock(list(coordinator.data.values()))


class TedeeBinarySensorEntity(TedeeDescriptionEntity, BinarySensorEntity):
    """Tedee sensor entity."""

    entity_description: TedeeBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._lock)

    @property
    def available(self) -> bool:
        """Return true if the binary sensor is available."""
        return self.entity_description.available_fn(self._lock) and super().available
