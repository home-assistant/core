"""Support for select entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from gardena_bluetooth.const import (
    AquaContour,
    AquaContourPosition,
    AquaContourWatering,
)
from gardena_bluetooth.parse import CharacteristicInt

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GardenaBluetoothConfigEntry
from .entity import GardenaBluetoothDescriptorEntity


def _enum_to_int(enum: type[IntEnum]) -> dict[str, int]:
    return {member.name.lower(): member.value for member in enum}


def _reverse_dict(value: dict[str, int]) -> dict[int, str]:
    return {value: key for key, value in value.items()}


@dataclass(frozen=True, kw_only=True)
class GardenaBluetoothSelectEntityDescription(SelectEntityDescription):
    """Description of entity."""

    key: str = field(init=False)
    char: CharacteristicInt
    option_to_number: dict[str, int]
    number_to_option: dict[int, str] = field(init=False)

    def __post_init__(self):
        """Initialize calculated fields."""
        object.__setattr__(self, "key", self.char.unique_id)
        object.__setattr__(self, "options", list(self.option_to_number.keys()))
        object.__setattr__(
            self, "number_to_option", _reverse_dict(self.option_to_number)
        )

    @property
    def context(self) -> set[str]:
        """Context needed for update coordinator."""
        return {self.char.uuid}


DESCRIPTIONS = (
    GardenaBluetoothSelectEntityDescription(
        translation_key="watering_active",
        char=AquaContourWatering.watering_active,
        option_to_number=_enum_to_int(AquaContourWatering.watering_active.enum),
    ),
    GardenaBluetoothSelectEntityDescription(
        translation_key="operation_mode",
        char=AquaContour.operation_mode,
        option_to_number=_enum_to_int(AquaContour.operation_mode.enum),
    ),
    GardenaBluetoothSelectEntityDescription(
        translation_key="active_position",
        char=AquaContourPosition.active_position,
        option_to_number={
            "position_1": 1,
            "position_2": 2,
            "position_3": 3,
            "position_4": 4,
            "position_5": 5,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaBluetoothConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select based on a config entry."""
    coordinator = entry.runtime_data
    entities = [
        GardenaBluetoothSelectEntity(coordinator, description, description.context)
        for description in DESCRIPTIONS
        if description.char.unique_id in coordinator.characteristics
    ]
    async_add_entities(entities)


class GardenaBluetoothSelectEntity(GardenaBluetoothDescriptorEntity, SelectEntity):
    """Representation of a select entity."""

    entity_description: GardenaBluetoothSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        char = self.entity_description.char
        value = self.coordinator.get_cached(char)
        if value is None:
            return None
        return self.entity_description.number_to_option.get(value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        char = self.entity_description.char
        value = self.entity_description.option_to_number[option]
        await self.coordinator.write(char, value)
        self.async_write_ha_state()
