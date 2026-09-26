"""Arcam FMJ select entities."""

from typing import override

from arcam.fmj.codecs import RoomEqMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import ArcamFmjEntity, convert_exception

PARALLEL_UPDATES = 1

_DEFAULT_ROOM_EQ_NAMES = ("EQ1", "EQ2", "EQ3")
_ROOM_EQ_MODES = (RoomEqMode.EQ1, RoomEqMode.EQ2, RoomEqMode.EQ3)

ROOM_EQ_DESCRIPTION = SelectEntityDescription(
    key="room_equalization",
    translation_key="room_equalization",
)


def _room_eq_names(coordinator: ArcamFmjCoordinator) -> tuple[str, ...]:
    """Return a name for each available Room EQ profile slot."""
    names = coordinator.state.get_room_eq_names() or []
    return (
        tuple(
            name or default
            for name, default in zip(
                names[: len(_DEFAULT_ROOM_EQ_NAMES)],
                _DEFAULT_ROOM_EQ_NAMES,
                strict=False,
            )
        )
        + _DEFAULT_ROOM_EQ_NAMES[len(names) :]
    )


def _room_eq_options(
    coordinator: ArcamFmjCoordinator,
) -> tuple[tuple[RoomEqMode, str], ...]:
    """Return uniquely labelled Room EQ profile options."""
    return tuple(
        (mode, f"{mode.name}: {name}")
        for mode, name in zip(
            _ROOM_EQ_MODES,
            _room_eq_names(coordinator),
            strict=True,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ select entities from a config entry."""
    async_add_entities(
        ArcamFmjRoomEqSelect(coordinator)
        for coordinator in config_entry.runtime_data.coordinators.values()
    )


class ArcamFmjRoomEqSelect(ArcamFmjEntity, SelectEntity):
    """Enable or disable the receiver's Dirac room equalization."""

    entity_description = ROOM_EQ_DESCRIPTION

    def __init__(self, coordinator: ArcamFmjCoordinator) -> None:
        """Initialize the room-EQ selector."""
        super().__init__(coordinator, ROOM_EQ_DESCRIPTION)

    @property
    @override
    def options(self) -> list[str]:
        """Return available room-EQ options."""
        options = [
            "Off",
            *(option for _mode, option in _room_eq_options(self.coordinator)),
        ]
        if self.coordinator.state.get_room_equalization() == RoomEqMode.NOT_CALCULATED:
            options.append("Not calculated")
        return options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently active room-EQ option."""
        mode = self.coordinator.state.get_room_equalization()
        if mode is None:
            return None
        if mode in _ROOM_EQ_MODES:
            return dict(_room_eq_options(self.coordinator))[mode]
        return {
            RoomEqMode.OFF: "Off",
            RoomEqMode.NOT_CALCULATED: "Not calculated",
        }.get(mode)

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select a Dirac room-EQ profile on the receiver."""
        mode: RoomEqMode | None = None
        if option == "Off":
            mode = RoomEqMode.OFF
        elif option == "Not calculated":
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_room_equalization",
                translation_placeholders={"room_equalization": option},
            )
        else:
            mode = next(
                (
                    profile_mode
                    for profile_mode, profile_option in _room_eq_options(
                        self.coordinator
                    )
                    if profile_option == option
                ),
                None,
            )

        if mode is not None:
            await self.coordinator.state.set_room_equalization(mode)
            self.async_write_ha_state()
            return

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_room_equalization",
            translation_placeholders={"room_equalization": option},
        )
