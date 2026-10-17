"""Arcam FMJ select entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from typing import Any, override

from arcam.fmj.codecs import RoomEqMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import ArcamFmjEntity, convert_exception

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ArcamFmjEnumSelectEntityDescription[EnumT: Enum](SelectEntityDescription):
    """Description for a select entity backed by enum values."""

    options_fn: Callable[[ArcamFmjCoordinator], dict[str, EnumT]]
    current_value_fn: Callable[[ArcamFmjCoordinator], EnumT | None]
    set_value_fn: Callable[[ArcamFmjCoordinator, EnumT], Coroutine[Any, Any, None]]
    invalid_option_translation_key: str
    invalid_option_placeholder: str
    read_only_values: frozenset[EnumT] = frozenset()


ROOM_EQ_DESCRIPTION = ArcamFmjEnumSelectEntityDescription[RoomEqMode](
    key="room_equalization",
    translation_key="room_equalization",
    options_fn=lambda coordinator: _room_eq_options(coordinator),
    current_value_fn=lambda coordinator: coordinator.state.get_room_equalization(),
    set_value_fn=lambda coordinator, mode: coordinator.state.set_room_equalization(
        mode
    ),
    read_only_values=frozenset({RoomEqMode.NOT_CALCULATED}),
    invalid_option_translation_key="unsupported_room_equalization",
    invalid_option_placeholder="room_equalization",
)


def _room_eq_options(coordinator: ArcamFmjCoordinator) -> dict[str, RoomEqMode]:
    """Map Room EQ option labels to their enum values."""
    names = coordinator.state.get_room_eq_names() or []
    options = {"off": RoomEqMode.OFF}
    for index, mode in enumerate((RoomEqMode.EQ1, RoomEqMode.EQ2, RoomEqMode.EQ3)):
        name = names[index] if index < len(names) else None
        option = f"{mode.name}: {name}" if name else mode.name
        options[option] = mode

    if coordinator.state.get_room_equalization() == RoomEqMode.NOT_CALCULATED:
        options["not_calculated"] = RoomEqMode.NOT_CALCULATED

    return options


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ select entities from a config entry."""
    async_add_entities(
        ArcamFmjEnumSelectEntity(coordinator, ROOM_EQ_DESCRIPTION)
        for coordinator in config_entry.runtime_data.coordinators.values()
        if coordinator.state.zn == 1
    )


class ArcamFmjEnumSelectEntity[EnumT: Enum](ArcamFmjEntity, SelectEntity):
    """A select entity whose options map to enum values."""

    entity_description: ArcamFmjEnumSelectEntityDescription[EnumT]

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjEnumSelectEntityDescription[EnumT],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, description)

    @property
    @override
    def options(self) -> list[str]:
        """Return the available select options."""
        return list(self.entity_description.options_fn(self.coordinator))

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option matching the current enum value."""
        current_value = self.entity_description.current_value_fn(self.coordinator)
        return next(
            (
                option
                for option, value in self.entity_description.options_fn(
                    self.coordinator
                ).items()
                if value == current_value
            ),
            None,
        )

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select the enum value represented by an option."""
        values = self.entity_description.options_fn(self.coordinator)
        if (
            option not in values
            or values[option] in self.entity_description.read_only_values
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=self.entity_description.invalid_option_translation_key,
                translation_placeholders={
                    self.entity_description.invalid_option_placeholder: option
                },
            )

        await self.entity_description.set_value_fn(self.coordinator, values[option])
        self.async_write_ha_state()
