"""Entity classes for the infrared integration."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import final

from infrared_protocols.commands import Command as InfraredCommand
from propcache.api import cached_property

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.deprecation import deprecated_class
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class InfraredDeviceClass(StrEnum):
    """Device class for infrared entities."""

    EMITTER = "emitter"
    RECEIVER = "receiver"


@dataclass(frozen=True, slots=True)
class InfraredReceivedSignal:
    """Represents a received IR signal."""

    timings: list[int]
    modulation: int | None = None


class InfraredEmitterEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared emitter entities."""


class InfraredEmitterEntity(RestoreEntity):
    """Base class for infrared emitter entities."""

    entity_description: InfraredEmitterEntityDescription
    _attr_device_class: InfraredDeviceClass = InfraredDeviceClass.EMITTER
    _attr_should_poll = False
    _attr_state: None = None

    __last_command_sent: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_command_sent

    @final
    async def async_send_command_internal(self, command: InfraredCommand) -> None:
        """Send an IR command and update state.

        Should not be overridden, handles setting last sent timestamp.
        """
        await self.async_send_command(command)
        self.__last_command_sent = dt_util.utcnow().isoformat(timespec="milliseconds")
        self.async_write_ha_state()

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the infrared entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__last_command_sent = state.state

    @abstractmethod
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Args:
            command: The IR command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """


class InfraredReceiverEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared receiver entities."""


class InfraredReceiverEntity(RestoreEntity):
    """Base class for infrared receiver entities."""

    entity_description: InfraredReceiverEntityDescription
    _attr_device_class: InfraredDeviceClass = InfraredDeviceClass.RECEIVER
    _attr_should_poll = False
    _attr_state: None = None

    __last_signal_received: str | None = None

    @cached_property
    def __signal_callbacks(self) -> set[Callable[[InfraredReceivedSignal], None]]:
        """Subscriber callback set, lazily initialized on first access."""
        return set()

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_signal_received

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the infrared entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
        ):
            self.__last_signal_received = state.state

    @final
    def _handle_received_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal.

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
        signal_callback: Callable[[InfraredReceivedSignal], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to received IR signals.

        Returns a callable to unsubscribe.
        """
        callbacks = self.__signal_callbacks
        callbacks.add(signal_callback)

        @callback
        def remove_callback() -> None:
            callbacks.discard(signal_callback)

        return remove_callback


@deprecated_class(
    "homeassistant.components.infrared.InfraredEmitterEntityDescription",
    breaks_in_ha_version="2027.6",
)
class InfraredEntityDescription(InfraredEmitterEntityDescription):
    """Deprecated alias for InfraredEmitterEntityDescription."""


@deprecated_class(
    "homeassistant.components.infrared.InfraredEmitterEntity",
    breaks_in_ha_version="2027.6",
)
class InfraredEntity(InfraredEmitterEntity):
    """Deprecated alias for InfraredEmitterEntity."""
