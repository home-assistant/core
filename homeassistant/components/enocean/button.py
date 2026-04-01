"""Support for EnOcean trigger button entities."""

from __future__ import annotations

from enocean_async import (
    EURID,
    CoverQueryPositionAndAngle,
    EntityType,
    Gateway,
    Instructable,
    QueryActuatorMeasurement,
    QueryActuatorStatus,
    TeachIn,  # codespell:ignore teachin
)
from enocean_async.semantics.instruction import Instruction

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import LIB_ENTITY_CATEGORY_MAP, EnOceanEntity

PARALLEL_UPDATES = 1

_INSTRUCTABLE_TO_INSTRUCTION: dict[Instructable, type[Instruction]] = {
    Instructable.QUERY_ACTUATOR_STATUS: QueryActuatorStatus,
    Instructable.QUERY_ACTUATOR_MEASUREMENT: QueryActuatorMeasurement,
    Instructable.COVER_QUERY_POSITION_AND_ANGLE: CoverQueryPositionAndAngle,
    Instructable.TEACH_IN: TeachIn,  # codespell:ignore teachin
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data

    entities = []
    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type != EntityType.TRIGGER:
                continue
            action = next(iter(entity.actions), None)
            if action is None or action not in _INSTRUCTABLE_TO_INSTRUCTION:
                continue
            entities.append(
                EnOceanButton(
                    eurid,
                    entity.id,
                    gateway,
                    _INSTRUCTABLE_TO_INSTRUCTION[action],
                    LIB_ENTITY_CATEGORY_MAP.get(entity.category),
                )
            )

    async_add_entities(entities)


class EnOceanButton(EnOceanEntity, ButtonEntity):
    """Representation of an EnOcean outbound trigger as a button."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        instruction_cls: type[Instruction],
        entity_category: EntityCategory | None,
    ) -> None:
        """Initialize the EnOcean trigger button."""
        super().__init__(address, entity_key, gateway)
        self._instruction_cls = instruction_cls
        self._attr_entity_category = entity_category

    async def async_press(self) -> None:
        """Send the trigger command to the device."""
        await self.gateway.send_command(
            self.address,
            self._instruction_cls(entity_id=self.entity_key),
        )
