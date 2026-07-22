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

from .common import async_setup_unit_entities
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MelCloudHomeBinarySensorEntityDescription[_UnitT: ATAUnit | ATWUnit](
    BinarySensorEntityDescription
):
    """Class to hold MELCloud Home binary sensor description."""

    state_fn: Callable[[_UnitT], bool | None]


def _common_sensor_descriptions[_UnitT: ATAUnit | ATWUnit](
    unit_type: type[_UnitT],
) -> tuple[MelCloudHomeBinarySensorEntityDescription[_UnitT], ...]:
    """Return the binary sensor descriptions shared by ATA and ATW units."""
    return (
        MelCloudHomeBinarySensorEntityDescription(
            key="error",
            translation_key="error",
            device_class=BinarySensorDeviceClass.PROBLEM,
            state_fn=lambda unit: unit.is_in_error,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        MelCloudHomeBinarySensorEntityDescription(
            key="standby",
            translation_key="standby",
            state_fn=lambda unit: unit.in_standby_mode,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        MelCloudHomeBinarySensorEntityDescription(
            key="holiday_mode",
            translation_key="holiday_mode",
            state_fn=lambda unit: (
                unit.holiday_mode.enabled if unit.holiday_mode else None
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        MelCloudHomeBinarySensorEntityDescription(
            key="frost_protection",
            translation_key="frost_protection",
            state_fn=lambda unit: (
                unit.frost_protection.enabled if unit.frost_protection else None
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        MelCloudHomeBinarySensorEntityDescription(
            key="overheat_protection",
            translation_key="overheat_protection",
            state_fn=lambda unit: (
                unit.overheat_protection.enabled if unit.overheat_protection else None
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )


ATA_SENSORS: tuple[MelCloudHomeBinarySensorEntityDescription[ATAUnit], ...] = (
    *_common_sensor_descriptions(ATAUnit),
)

ATW_SENSORS: tuple[MelCloudHomeBinarySensorEntityDescription[ATWUnit], ...] = (
    *_common_sensor_descriptions(ATWUnit),
    MelCloudHomeBinarySensorEntityDescription(
        key="forced_hot_water",
        translation_key="forced_hot_water",
        state_fn=lambda unit: unit.forced_hot_water_mode,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home binary sensors."""

    async_setup_unit_entities(
        entry.runtime_data,
        async_add_entities,
        lambda units: (
            ATABinarySensor(entry.runtime_data, entity_description, unit)
            for entity_description in ATA_SENSORS
            for unit in units
        ),
        lambda units: (
            ATWBinarySensor(entry.runtime_data, entity_description, unit)
            for entity_description in ATW_SENSORS
            for unit in units
        ),
    )


class ATABinarySensor(MelCloudHomeATAUnitEntity, BinarySensorEntity):
    """Representation of a MELCloud Home ATA binary sensor."""

    entity_description: MelCloudHomeBinarySensorEntityDescription[ATAUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeBinarySensorEntityDescription[ATAUnit],
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

    entity_description: MelCloudHomeBinarySensorEntityDescription[ATWUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeBinarySensorEntityDescription[ATWUnit],
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
