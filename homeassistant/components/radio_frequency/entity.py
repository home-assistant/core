"""Base entity for the radio frequency integration."""

from abc import abstractmethod
from typing import final

from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util


class RadioFrequencyTransmitterEntityDescription(
    EntityDescription, frozen_or_thawed=True
):
    """Describes radio frequency transmitter entities."""


class RadioFrequencyTransmitterEntity(RestoreEntity):
    """Base class for radio frequency transmitter entities."""

    entity_description: RadioFrequencyTransmitterEntityDescription
    _attr_should_poll = False
    _attr_state: None = None

    __last_command_sent: str | None = None

    @property
    @abstractmethod
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return list of (min_hz, max_hz) tuples."""

    @callback
    @final
    def supports_frequency(self, frequency: int) -> bool:
        """Return whether the transmitter supports the given frequency."""
        return any(
            low <= frequency <= high for low, high in self.supported_frequency_ranges
        )

    @callback
    @final
    def supports_modulation(self, modulation: ModulationType) -> bool:
        """Return whether the transmitter supports the given modulation."""
        return modulation == ModulationType.OOK

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_command_sent

    @final
    async def async_send_command_internal(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command and update state.

        Should not be overridden, handles setting last sent timestamp.
        """
        await self.async_send_command(command)
        self.__last_command_sent = dt_util.utcnow().isoformat(timespec="milliseconds")
        self.async_write_ha_state()

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the radio frequency entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__last_command_sent = state.state

    @abstractmethod
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command.

        Args:
            command: The RF command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """
