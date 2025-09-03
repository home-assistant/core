"""Support for select entities."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from togrill_bluetooth.packets import (
    GrillType,
    PacketA8Notify,
    PacketA303Write,
    PacketWrite,
    Taste,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ToGrillConfigEntry
from .const import CONF_PROBE_COUNT, MAX_PROBE_COUNT
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0

OPTION_NONE = "none"


@dataclass(kw_only=True, frozen=True)
class ToGrillSelectEntityDescription(SelectEntityDescription):
    """Description of entity."""

    get_value: Callable[[ToGrillCoordinator], str | None]
    set_packet: Callable[[ToGrillCoordinator, str], PacketWrite]
    entity_supported: Callable[[Mapping[str, Any]], bool] = lambda _: True
    probe_number: int | None = None


_ENUM = TypeVar("_ENUM", bound=Enum)


def _get_enum_from_name(type_: type[_ENUM], value: str) -> _ENUM | None:
    """Return enum value or None."""
    if value == OPTION_NONE:
        return None
    return type_[value.upper()]


def _get_enum_from_value(type_: type[_ENUM], value: int | None) -> _ENUM | None:
    """Return enum value or None."""
    if value is None:
        return None
    try:
        return type_(value)
    except ValueError:
        return None


def _get_enum_options(type_: type[_ENUM]) -> list[str]:
    """Return a list of enum options."""
    values = [OPTION_NONE]
    values.extend(option.name.lower() for option in type_)
    return values


def _get_probe_descriptions(
    probe_number: int,
) -> Generator[ToGrillSelectEntityDescription]:
    def _get_grill_info(
        coordinator: ToGrillCoordinator,
    ) -> tuple[GrillType | None, Taste | None]:
        if not (packet := coordinator.get_packet(PacketA8Notify, probe_number)):
            return None, None

        return _get_enum_from_value(GrillType, packet.grill_type), _get_enum_from_value(
            Taste, packet.taste
        )

    def _set_grill_type(coordinator: ToGrillCoordinator, value: str) -> PacketWrite:
        _, taste = _get_grill_info(coordinator)
        grill_type = _get_enum_from_name(GrillType, value)
        return PacketA303Write(probe=probe_number, grill_type=grill_type, taste=taste)

    def _set_taste(coordinator: ToGrillCoordinator, value: str) -> PacketWrite:
        grill_type, _ = _get_grill_info(coordinator)
        taste = _get_enum_from_name(Taste, value)
        return PacketA303Write(probe=probe_number, grill_type=grill_type, taste=taste)

    def _get_grill_type(coordinator: ToGrillCoordinator) -> str | None:
        grill_type, _ = _get_grill_info(coordinator)
        if grill_type is None:
            return OPTION_NONE
        return grill_type.name.lower()

    def _get_taste(coordinator: ToGrillCoordinator) -> str | None:
        _, taste = _get_grill_info(coordinator)
        if taste is None:
            return OPTION_NONE
        return taste.name.lower()

    yield ToGrillSelectEntityDescription(
        key=f"grill_type_{probe_number}",
        translation_key="grill_type",
        options=_get_enum_options(GrillType),
        set_packet=_set_grill_type,
        get_value=_get_grill_type,
        entity_supported=lambda x: probe_number <= x[CONF_PROBE_COUNT],
        probe_number=probe_number,
    )

    yield ToGrillSelectEntityDescription(
        key=f"taste_{probe_number}",
        translation_key="taste",
        options=_get_enum_options(Taste),
        set_packet=_set_taste,
        get_value=_get_taste,
        entity_supported=lambda x: probe_number <= x[CONF_PROBE_COUNT],
        probe_number=probe_number,
    )


ENTITY_DESCRIPTIONS = (
    *[
        description
        for probe_number in range(1, MAX_PROBE_COUNT + 1)
        for description in _get_probe_descriptions(probe_number)
    ],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        ToGrillSelect(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        if entity_description.entity_supported(entry.data)
    )


class ToGrillSelect(ToGrillEntity, SelectEntity):
    """Representation of a select entity."""

    entity_description: ToGrillSelectEntityDescription

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
        entity_description: ToGrillSelectEntityDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, probe_number=entity_description.probe_number)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""

        return self.entity_description.get_value(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        """Set value on device."""

        packet = self.entity_description.set_packet(self.coordinator, option)
        await self._write_packet(packet)
