"""Support for EnOcean trigger button entities."""

from __future__ import annotations

from enocean_async import EURID, INSTRUCTION_FOR, EntityType, Gateway
from enocean_async.semantics.instruction import Instruction

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import LIB_ENTITY_CATEGORY_MAP, EnOceanEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid = gateway.eurid

    entities: list[EnOceanButton] = []

    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type != EntityType.TRIGGER:
                continue
            action = next(iter(entity.actions), None)
            if action is None or action not in INSTRUCTION_FOR:
                continue
            entities.append(
                EnOceanButton(
                    eurid,
                    entity.id,
                    gateway,
                    INSTRUCTION_FOR[action],
                    LIB_ENTITY_CATEGORY_MAP.get(entity.category),
                )
            )
        if gateway_eurid is not None:
            for entity in spec.gateway_entities:
                if entity.entity_type != EntityType.TRIGGER:
                    continue
                action = next(iter(entity.actions), None)
                if action is None or action not in INSTRUCTION_FOR:
                    continue
                entities.append(
                    EnOceanButton(
                        eurid,
                        entity.id,
                        gateway,
                        INSTRUCTION_FOR[action],
                        LIB_ENTITY_CATEGORY_MAP.get(entity.category),
                        is_gateway_command=True,
                    )
                )

    if gateway_eurid is not None:
        for entity in gateway.gateway_entities:
            if entity.entity_type != EntityType.TRIGGER:
                continue
            action = next(iter(entity.actions), None)
            if action is None or action not in INSTRUCTION_FOR:
                continue
            entities.append(
                EnOceanButton(
                    gateway_eurid,
                    entity.id,
                    gateway,
                    INSTRUCTION_FOR[action],
                    LIB_ENTITY_CATEGORY_MAP.get(entity.category),
                    is_gateway_command=True,
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
        is_gateway_command: bool = False,
    ) -> None:
        """Initialize the EnOcean trigger button."""
        super().__init__(address, entity_key, gateway)
        self._instruction_cls = instruction_cls
        self._attr_entity_category = entity_category
        self._is_gateway_command = is_gateway_command
        if is_gateway_command:
            self._track_gateway_availability = False
            self._attr_available = True

    async def async_press(self) -> None:
        """Send the trigger command."""
        instruction = self._instruction_cls(entity_id=self.entity_key)
        if self._is_gateway_command:
            await self.gateway.gateway_command(instruction)
        else:
            await self.gateway.send_command(self.address, instruction)
