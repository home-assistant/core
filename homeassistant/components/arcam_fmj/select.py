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

ROOM_EQ_DESCRIPTION = SelectEntityDescription(
    key="room_equalization",
    translation_key="room_equalization",
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
        names = self.coordinator.state.get_room_eq_names()
        if not names:
            names = list(_DEFAULT_ROOM_EQ_NAMES)
        return ["Off", *names[:3]]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently active room-EQ option."""
        mode = self.coordinator.state.get_room_equalization()
        if mode is None:
            return None
        if mode == RoomEqMode.OFF:
            return "Off"
        if mode in (RoomEqMode.EQ1, RoomEqMode.EQ2, RoomEqMode.EQ3):
            names = self.coordinator.state.get_room_eq_names()
            index = mode.value - RoomEqMode.EQ1.value
            if names and index < len(names):
                return names[index]
            return _DEFAULT_ROOM_EQ_NAMES[index]
        if mode == RoomEqMode.NOT_CALCULATED:
            return "Not calculated"
        return None

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select a Dirac room-EQ profile on the receiver."""
        if option == "Off":
            mode = RoomEqMode.OFF
        else:
            names = self.coordinator.state.get_room_eq_names() or []
            available_names = names[:3] or list(_DEFAULT_ROOM_EQ_NAMES)
            mode = next(
                (
                    profile_mode
                    for profile_mode, profile_name in zip(
                        (RoomEqMode.EQ1, RoomEqMode.EQ2, RoomEqMode.EQ3),
                        available_names,
                        strict=False,
                    )
                    if profile_name == option
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
