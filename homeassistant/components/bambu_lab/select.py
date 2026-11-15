"""Select platform for the Bambu Lab integration."""

from typing import override

from aiobambulab import BambuLabClient, PrintState, SpeedProfile

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BambuLabConfigEntry
from .entity import BambuLabEntity, command

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select of a Bambu Lab printer."""
    async_add_entities([BambuLabPrintSpeedSelect(entry.runtime_data)])


class BambuLabPrintSpeedSelect(BambuLabEntity, SelectEntity):
    """The speed profile of a Bambu Lab printer."""

    _attr_translation_key = "print_speed"
    _attr_options = [profile.value for profile in SpeedProfile]

    def __init__(self, client: BambuLabClient) -> None:
        """Initialize the select."""
        super().__init__(client)
        self._attr_unique_id = f"{client.serial}_print_speed"

    @override
    @property
    def available(self) -> bool:
        """Return whether the printer can change its speed now."""
        state = self._client.state
        return (
            super().available
            and state.accepts_commands
            and state.print_state is PrintState.PRINTING
        )

    @override
    @property
    def current_option(self) -> str | None:
        """Return the speed profile of the printer."""
        return self._client.state.speed_profile

    @override
    @command
    async def async_select_option(self, option: str) -> None:
        """Set the speed profile of the printer."""
        await self._client.set_speed_profile(SpeedProfile(option))
