"""Button platform for the Bambu Lab integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from aiobambulab import BambuLabClient, PrintState

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BambuLabConfigEntry
from .entity import BambuLabEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BambuLabButtonEntityDescription(ButtonEntityDescription):
    """Describe a Bambu Lab button."""

    press_fn: Callable[[BambuLabClient], Awaitable[None]]
    print_states: frozenset[PrintState]


BUTTONS: tuple[BambuLabButtonEntityDescription, ...] = (
    BambuLabButtonEntityDescription(
        key="pause_print",
        translation_key="pause_print",
        press_fn=lambda client: client.pause_print(),
        print_states=frozenset({PrintState.PRINTING}),
    ),
    BambuLabButtonEntityDescription(
        key="resume_print",
        translation_key="resume_print",
        press_fn=lambda client: client.resume_print(),
        print_states=frozenset({PrintState.PAUSED}),
    ),
    BambuLabButtonEntityDescription(
        key="stop_print",
        translation_key="stop_print",
        press_fn=lambda client: client.stop_print(),
        print_states=frozenset({PrintState.PRINTING, PrintState.PAUSED}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of a Bambu Lab printer."""
    client = entry.runtime_data

    async_add_entities(BambuLabButton(client, description) for description in BUTTONS)


class BambuLabButton(BambuLabEntity, ButtonEntity):
    """A button of a Bambu Lab printer."""

    entity_description: BambuLabButtonEntityDescription

    def __init__(
        self, client: BambuLabClient, description: BambuLabButtonEntityDescription
    ) -> None:
        """Initialize the button."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.serial}_{description.key}"

    @override
    @property
    def available(self) -> bool:
        """Return whether the printer can do this now."""
        state = self._client.state
        return (
            super().available
            and state.accepts_commands
            and state.print_state in self.entity_description.print_states
        )

    @override
    @command
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self._client)
