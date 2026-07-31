"""Switch platform for MELCloud Home."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import async_setup_unit_entities, perform_action, unit_ids
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MelCloudHomeSwitchEntityDescription[_UnitT: ATAUnit | ATWUnit](
    SwitchEntityDescription
):
    """Class to hold MELCloud Home switch description."""

    available_fn: Callable[[_UnitT], bool]
    is_on_fn: Callable[[_UnitT], bool | None]
    turn_on_fn: Callable[[MELCloudHome, _UnitT], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[MELCloudHome, _UnitT], Coroutine[Any, Any, None]]


def _switch_descriptions[_UnitT: ATAUnit | ATWUnit](
    unit_type: type[_UnitT],
) -> tuple[MelCloudHomeSwitchEntityDescription[_UnitT], ...]:
    """Return the switch descriptions for a unit type."""
    return (
        MelCloudHomeSwitchEntityDescription(
            key="frost_protection",
            translation_key="frost_protection",
            device_class=SwitchDeviceClass.SWITCH,
            entity_category=EntityCategory.CONFIG,
            available_fn=lambda unit: unit.frost_protection is not None,
            is_on_fn=lambda unit: (
                unit.frost_protection.enabled if unit.frost_protection else None
            ),
            turn_on_fn=lambda client, unit: client.set_frost_protection(
                enabled=True,
                min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
                max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
                **unit_ids(unit),
            ),
            turn_off_fn=lambda client, unit: client.set_frost_protection(
                enabled=False,
                min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
                max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
                **unit_ids(unit),
            ),
        ),
        MelCloudHomeSwitchEntityDescription(
            key="overheat_protection",
            translation_key="overheat_protection",
            device_class=SwitchDeviceClass.SWITCH,
            entity_category=EntityCategory.CONFIG,
            available_fn=lambda unit: unit.overheat_protection is not None,
            is_on_fn=lambda unit: (
                unit.overheat_protection.enabled if unit.overheat_protection else None
            ),
            turn_on_fn=lambda client, unit: client.set_overheat_protection(
                enabled=True,
                min_temp=unit.overheat_protection.min
                if unit.overheat_protection
                else 0.0,
                max_temp=unit.overheat_protection.max
                if unit.overheat_protection
                else 0.0,
                **unit_ids(unit),
            ),
            turn_off_fn=lambda client, unit: client.set_overheat_protection(
                enabled=False,
                min_temp=unit.overheat_protection.min
                if unit.overheat_protection
                else 0.0,
                max_temp=unit.overheat_protection.max
                if unit.overheat_protection
                else 0.0,
                **unit_ids(unit),
            ),
        ),
    )


ATA_SWITCHES: tuple[MelCloudHomeSwitchEntityDescription[ATAUnit], ...] = (
    _switch_descriptions(ATAUnit)
)
ATW_SWITCHES: tuple[MelCloudHomeSwitchEntityDescription[ATWUnit], ...] = (
    _switch_descriptions(ATWUnit)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home switches."""

    async_setup_unit_entities(
        entry.runtime_data,
        async_add_entities,
        lambda units: (
            ATASwitch(entry.runtime_data, entity_description, unit)
            for entity_description in ATA_SWITCHES
            for unit in units
        ),
        lambda units: (
            ATWSwitch(entry.runtime_data, entity_description, unit)
            for entity_description in ATW_SWITCHES
            for unit in units
        ),
    )


class ATASwitch(MelCloudHomeATAUnitEntity, SwitchEntity):
    """Representation of a MELCloud Home ATA switch."""

    entity_description: MelCloudHomeSwitchEntityDescription[ATAUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeSwitchEntityDescription[ATAUnit],
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
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.unit)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the protection."""
        await perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.client, self.unit),
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the protection."""
        await perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.client, self.unit),
        )


class ATWSwitch(MelCloudHomeATWUnitEntity, SwitchEntity):
    """Representation of a MELCloud Home ATW switch."""

    entity_description: MelCloudHomeSwitchEntityDescription[ATWUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeSwitchEntityDescription[ATWUnit],
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
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.unit)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the protection."""
        await perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.client, self.unit),
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the protection."""
        await perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.client, self.unit),
        )
