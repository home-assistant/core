"""Tedee sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from aiotedee import TedeeLock
from aiotedee.lock import TedeeLockState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TedeeConfigEntry
from .entity import TedeeDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class TedeeBinarySensorEntityDescription(
    BinarySensorEntityDescription,
):
    """Describes Tedee binary sensor entity."""

    is_on_fn: Callable[[TedeeLock], bool | None]


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
        is_on_fn=lambda lock: lock.state == TedeeLockState.HALF_OPEN,
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
        is_on_fn=lambda lock: lock.state == TedeeLockState.UNCALIBRATED,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TedeeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tedee sensor entity."""
    coordinator = entry.runtime_data

    async_add_entities(
        TedeeBinarySensorEntity(lock, coordinator, entity_description)
        for lock in coordinator.data.values()
        for entity_description in ENTITIES
    )

    def _async_add_new_lock(lock_id: int) -> None:
        lock = coordinator.data[lock_id]
        async_add_entities(
            TedeeBinarySensorEntity(lock, coordinator, entity_description)
            for entity_description in ENTITIES
        )

    coordinator.new_lock_callbacks.append(_async_add_new_lock)


class TedeeBinarySensorEntity(TedeeDescriptionEntity, BinarySensorEntity):
    """Tedee sensor entity."""

    entity_description: TedeeBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._lock)
