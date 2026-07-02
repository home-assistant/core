"""Binary sensor platform for MELCloud Home."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiomelcloudhome import ATAUnit, ATWUnit

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ATABinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold MELCloud Home ATA binary sensor description."""

    state_fn: Callable[[ATAUnit], bool | None]


@dataclass(frozen=True, kw_only=True)
class ATWBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold MELCloud Home ATW binary sensor description."""

    state_fn: Callable[[ATWUnit], bool | None]


ATA_SENSORS: tuple[ATABinarySensorEntityDescription, ...] = (
    ATABinarySensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_fn=lambda unit: unit.is_in_error,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATABinarySensorEntityDescription(
        key="standby",
        translation_key="standby",
        state_fn=lambda unit: unit.in_standby_mode,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATABinarySensorEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        state_fn=lambda unit: (
            unit.frost_protection.enabled if unit.frost_protection else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATABinarySensorEntityDescription(
        key="overheat_protection",
        translation_key="overheat_protection",
        state_fn=lambda unit: (
            unit.overheat_protection.enabled if unit.overheat_protection else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATABinarySensorEntityDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        state_fn=lambda unit: unit.holiday_mode.enabled if unit.holiday_mode else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ATW_SENSORS: tuple[ATWBinarySensorEntityDescription, ...] = (
    ATWBinarySensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_fn=lambda unit: unit.is_in_error,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATWBinarySensorEntityDescription(
        key="standby",
        translation_key="standby",
        state_fn=lambda unit: unit.in_standby_mode,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATWBinarySensorEntityDescription(
        key="forced_hot_water",
        translation_key="forced_hot_water",
        state_fn=lambda unit: unit.forced_hot_water_mode,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATWBinarySensorEntityDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        state_fn=lambda unit: unit.holiday_mode.enabled if unit.holiday_mode else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home binary sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(
            ATABinarySensor(coordinator, entity_description, unit)
            for entity_description in ATA_SENSORS
            for unit in units
        )

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        async_add_entities(
            ATWBinarySensor(coordinator, entity_description, unit)
            for entity_description in ATW_SENSORS
            for unit in units
        )

    coordinator.new_ata_callbacks.append(_async_add_new_ata_units)
    coordinator.new_atw_callbacks.append(_async_add_new_atw_units)

    _async_add_new_ata_units(list(coordinator.ata_units.values()))
    _async_add_new_atw_units(list(coordinator.atw_units.values()))


class ATABinarySensor(MelCloudHomeATAUnitEntity, BinarySensorEntity):
    """Representation of a MELCloud Home ATA binary sensor."""

    entity_description: ATABinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATABinarySensorEntityDescription,
        unit: ATAUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.unit)


class ATWBinarySensor(MelCloudHomeATWUnitEntity, BinarySensorEntity):
    """Representation of a MELCloud Home ATW binary sensor."""

    entity_description: ATWBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATWBinarySensorEntityDescription,
        unit: ATWUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.unit)
