"""Base entity for the radio frequency integration."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import final, override

from propcache.api import cached_property
from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class RadioFrequencyDeviceClass(StrEnum):
    """Device class for radio frequency entities."""

    TRANSMITTER = "transmitter"
    RECEIVER = "receiver"


@dataclass(frozen=True, slots=True)
class RadioFrequencyReceivedSignal:
    """Represents a received RF signal."""

    timings: list[int]
    frequency: int | None = None
    modulation: ModulationType = ModulationType.OOK


class _RadioFrequencyEntity(RestoreEntity):
    """Common base for radio frequency transmitter and receiver entities."""

    _attr_device_class: RadioFrequencyDeviceClass
    _attr_should_poll = False
    _attr_state: None = None

    @override
    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class."""
        return self.device_class is not None

    @property
    @abstractmethod
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return list of (min_hz, max_hz) tuples."""

    @callback
    @final
    def supports_frequency(self, frequency: int) -> bool:
        """Return whether the entity supports the given frequency."""
        return any(
            low <= frequency <= high for low, high in self.supported_frequency_ranges
        )

    @callback
    @final
    def supports_modulation(self, modulation: ModulationType) -> bool:
        """Return whether the entity supports the given modulation."""
        return modulation == ModulationType.OOK


class RadioFrequencyTransmitterEntityDescription(
    EntityDescription, frozen_or_thawed=True
):
    """Describes radio frequency transmitter entities."""


class RadioFrequencyTransmitterEntity(_RadioFrequencyEntity):
    """Base class for radio frequency transmitter entities."""

    entity_description: RadioFrequencyTransmitterEntityDescription
    _attr_device_class = RadioFrequencyDeviceClass.TRANSMITTER

    __last_command_sent: str | None = None

    @property
    @final
    @override
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
    @override
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


class RadioFrequencyReceiverEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes radio frequency receiver entities."""


class RadioFrequencyReceiverEntity(_RadioFrequencyEntity):
    """Base class for radio frequency receiver entities."""

    entity_description: RadioFrequencyReceiverEntityDescription
    _attr_device_class = RadioFrequencyDeviceClass.RECEIVER

    __last_signal_received: str | None = None

    @cached_property
    def __signal_callbacks(
        self,
    ) -> set[Callable[[RadioFrequencyReceivedSignal], None]]:
        """Subscriber callback set, lazily initialized on first access."""
        return set()

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_signal_received

    @final
    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the radio frequency entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
        ):
            self.__last_signal_received = state.state

    @final
    def _handle_received_signal(self, signal: RadioFrequencyReceivedSignal) -> None:
        """Handle a received RF signal.

        Should not be overridden. To be called by platform implementations when a
        signal is received.
        """
        self.__last_signal_received = dt_util.utcnow().isoformat(
            timespec="milliseconds"
        )
        self.async_write_ha_state()
        for signal_callback in tuple(self.__signal_callbacks):
            try:
                signal_callback(signal)
            except Exception:
                _LOGGER.exception("Error in signal callback for %s", self.entity_id)

    @callback
    def async_subscribe_received_signal(
        self,
        signal_callback: Callable[[RadioFrequencyReceivedSignal], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to received RF signals.

        Returns a callable to unsubscribe.
        """
        callbacks = self.__signal_callbacks
        callbacks.add(signal_callback)

        @callback
        def remove_callback() -> None:
            callbacks.discard(signal_callback)

        return remove_callback
