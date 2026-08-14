"""Number platform for MELCloud Home."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import async_setup_unit_entities, perform_action, unit_ids
from .const import DOMAIN
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MelCloudHomeNumberEntityDescription[_UnitT: ATAUnit | ATWUnit](
    NumberEntityDescription
):
    """Class to hold MELCloud Home number description."""

    available_fn: Callable[[_UnitT], bool]
    value_fn: Callable[[_UnitT], float | None]
    set_value_fn: Callable[[MELCloudHome, _UnitT, float], Coroutine[Any, Any, None]]
    validate_fn: Callable[[_UnitT, float], str | None] | None = None


def _number_descriptions[_UnitT: ATAUnit | ATWUnit](
    unit_type: type[_UnitT],
    *,
    overheat_min_temp: float,
    overheat_max_temp: float,
) -> tuple[MelCloudHomeNumberEntityDescription[_UnitT], ...]:
    """Return the number descriptions for a unit type."""
    return (
        MelCloudHomeNumberEntityDescription(
            key="frost_protection_min_temp",
            translation_key="frost_protection_min_temp",
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.CONFIG,
            native_min_value=0.0,
            native_max_value=30.0,
            native_step=0.5,
            available_fn=lambda unit: (
                unit.frost_protection is not None and unit.frost_protection.enabled
            ),
            value_fn=lambda unit: (
                unit.frost_protection.min if unit.frost_protection else None
            ),
            set_value_fn=lambda client, unit, value: client.set_frost_protection(
                enabled=unit.frost_protection.enabled
                if unit.frost_protection
                else False,
                min_temp=value,
                max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
                **unit_ids(unit),
            ),
            validate_fn=lambda unit, value: (
                "temperature_min_exceeds_max"
                if unit.frost_protection and value >= unit.frost_protection.max
                else None
            ),
        ),
        MelCloudHomeNumberEntityDescription(
            key="frost_protection_max_temp",
            translation_key="frost_protection_max_temp",
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.CONFIG,
            native_min_value=0.0,
            native_max_value=30.0,
            native_step=0.5,
            available_fn=lambda unit: (
                unit.frost_protection is not None and unit.frost_protection.enabled
            ),
            value_fn=lambda unit: (
                unit.frost_protection.max if unit.frost_protection else None
            ),
            set_value_fn=lambda client, unit, value: client.set_frost_protection(
                enabled=unit.frost_protection.enabled
                if unit.frost_protection
                else False,
                min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
                max_temp=value,
                **unit_ids(unit),
            ),
            validate_fn=lambda unit, value: (
                "temperature_max_below_min"
                if unit.frost_protection and value <= unit.frost_protection.min
                else None
            ),
        ),
        MelCloudHomeNumberEntityDescription(
            key="overheat_protection_min_temp",
            translation_key="overheat_protection_min_temp",
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.CONFIG,
            native_min_value=overheat_min_temp,
            native_max_value=overheat_max_temp,
            native_step=0.5,
            available_fn=lambda unit: (
                unit.overheat_protection is not None
                and unit.overheat_protection.enabled
            ),
            value_fn=lambda unit: (
                unit.overheat_protection.min if unit.overheat_protection else None
            ),
            set_value_fn=lambda client, unit, value: client.set_overheat_protection(
                enabled=unit.overheat_protection.enabled
                if unit.overheat_protection
                else False,
                min_temp=value,
                max_temp=unit.overheat_protection.max
                if unit.overheat_protection
                else 0.0,
                **unit_ids(unit),
            ),
            validate_fn=lambda unit, value: (
                "temperature_min_exceeds_max"
                if unit.overheat_protection and value >= unit.overheat_protection.max
                else None
            ),
        ),
        MelCloudHomeNumberEntityDescription(
            key="overheat_protection_max_temp",
            translation_key="overheat_protection_max_temp",
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.CONFIG,
            native_min_value=overheat_min_temp,
            native_max_value=overheat_max_temp,
            native_step=0.5,
            available_fn=lambda unit: (
                unit.overheat_protection is not None
                and unit.overheat_protection.enabled
            ),
            value_fn=lambda unit: (
                unit.overheat_protection.max if unit.overheat_protection else None
            ),
            set_value_fn=lambda client, unit, value: client.set_overheat_protection(
                enabled=unit.overheat_protection.enabled
                if unit.overheat_protection
                else False,
                min_temp=unit.overheat_protection.min
                if unit.overheat_protection
                else 0.0,
                max_temp=value,
                **unit_ids(unit),
            ),
            validate_fn=lambda unit, value: (
                "temperature_max_below_min"
                if unit.overheat_protection and value <= unit.overheat_protection.min
                else None
            ),
        ),
    )


ATA_NUMBERS: tuple[MelCloudHomeNumberEntityDescription[ATAUnit], ...] = (
    _number_descriptions(ATAUnit, overheat_min_temp=31.0, overheat_max_temp=40.0)
)
ATW_NUMBERS: tuple[MelCloudHomeNumberEntityDescription[ATWUnit], ...] = (
    _number_descriptions(ATWUnit, overheat_min_temp=20.0, overheat_max_temp=60.0)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home numbers."""

    async_setup_unit_entities(
        entry.runtime_data,
        async_add_entities,
        lambda units: (
            ATANumber(entry.runtime_data, entity_description, unit)
            for entity_description in ATA_NUMBERS
            for unit in units
        ),
        lambda units: (
            ATWNumber(entry.runtime_data, entity_description, unit)
            for entity_description in ATW_NUMBERS
            for unit in units
        ),
    )


class ATANumber(MelCloudHomeATAUnitEntity, NumberEntity):
    """Representation of a MELCloud Home ATA number."""

    entity_description: MelCloudHomeNumberEntityDescription[ATAUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeNumberEntityDescription[ATAUnit],
        unit: ATAUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(self.unit)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.unit)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the protection temperature threshold."""
        if self.entity_description.validate_fn and (
            error_key := self.entity_description.validate_fn(self.unit, value)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
            )
        await perform_action(
            self.coordinator,
            self.entity_description.set_value_fn(
                self.coordinator.client, self.unit, value
            ),
        )


class ATWNumber(MelCloudHomeATWUnitEntity, NumberEntity):
    """Representation of a MELCloud Home ATW number."""

    entity_description: MelCloudHomeNumberEntityDescription[ATWUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeNumberEntityDescription[ATWUnit],
        unit: ATWUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(self.unit)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.unit)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the protection temperature threshold."""
        if self.entity_description.validate_fn and (
            error_key := self.entity_description.validate_fn(self.unit, value)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
            )
        await perform_action(
            self.coordinator,
            self.entity_description.set_value_fn(
                self.coordinator.client, self.unit, value
            ),
        )
