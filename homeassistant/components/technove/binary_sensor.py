"""Support for TechnoVE binary sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from technove import Station as TechnoVEStation

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TechnoVEConfigEntry
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity


@dataclass(frozen=True, kw_only=True)
class TechnoVEBinarySensorDescription(BinarySensorEntityDescription):
    """Describes TechnoVE binary sensor entity."""

    value_fn: Callable[[TechnoVEStation], bool | None]


BINARY_SENSORS = [
    TechnoVEBinarySensorDescription(
        key="conflict_in_sharing_config",
        translation_key="conflict_in_sharing_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.conflict_in_sharing_config,
    ),
    TechnoVEBinarySensorDescription(
        key="in_sharing_mode",
        translation_key="in_sharing_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.in_sharing_mode,
    ),
    TechnoVEBinarySensorDescription(
        key="is_battery_protected",
        translation_key="is_battery_protected",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.is_battery_protected,
    ),
    TechnoVEBinarySensorDescription(
        key="is_session_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda station: station.info.is_session_active,
    ),
    TechnoVEBinarySensorDescription(
        key="is_static_ip",
        translation_key="is_static_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda station: station.info.is_static_ip,
    ),
    TechnoVEBinarySensorDescription(
        key="update_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.UPDATE,
        value_fn=lambda station: not station.info.is_up_to_date,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TechnoVEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities(
        TechnoVEBinarySensorEntity(entry.runtime_data, description)
        for description in BINARY_SENSORS
    )


class TechnoVEBinarySensorEntity(TechnoVEEntity, BinarySensorEntity):
    """Defines a TechnoVE binary sensor entity."""

    entity_description: TechnoVEBinarySensorDescription

    def __init__(
        self,
        coordinator: TechnoVEDataUpdateCoordinator,
        description: TechnoVEBinarySensorDescription,
    ) -> None:
        """Initialize a TechnoVE binary sensor entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
