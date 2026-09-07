"""Event entity for the known commands a receiver picks up."""

import time
from typing import final, override

from homeassistant.components.event import EventEntity
from homeassistant.const import CONF_ID, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    State,
    callback,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event

from .commands import DATA_COMMANDS
from .entity import (
    DATA_RECEIVERS,
    SIGNAL_INFRARED_RECEIVER_ADDED,
    SIGNAL_INFRARED_RECEIVER_REMOVED,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)

# A remote repeats its frame for as long as the button is held, and some
# protocols send a command several times even for a short press. A command that
# comes back within this many seconds is the same press, not a new one. It is
# comfortably longer than the frame period of the common protocols, the slowest
# of which repeats about every 130 ms.
_REPEAT_WINDOW = 0.3


def _is_available(state: State | None) -> bool:
    """Return whether a state means the entity is available."""
    return state is not None and state.state != STATE_UNAVAILABLE


# Not in an event.py: the event entity is added by the event platform of the
# integration that provides the receiver, not by infrared itself.
@final
class InfraredCommandEventEntity(EventEntity):  # pylint: disable=home-assistant-enforce-class-module
    """Fires when its receiver picks up one of the known infrared commands.

    Added by the event platform of the integration that provides the receiver,
    which is identified by its unique id: the two entities are added
    independently, in either order.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "infrared_command"

    def __init__(self, receiver_unique_id: str, device_info: DeviceInfo) -> None:
        """Initialize the event entity."""
        self._receiver_unique_id = receiver_unique_id
        self._attr_unique_id = f"{receiver_unique_id}-commands"
        self._attr_device_info = device_info
        self._receiver: InfraredReceiverEntity | None = None
        self._receiver_key: tuple[str, str] | None = None
        self._receiver_subscriptions: list[CALLBACK_TYPE] = []
        self._last_received: dict[str, float] = {}

    @property
    @override
    def available(self) -> bool:
        """Return whether the receiver is there and available."""
        return self._receiver is not None and self._receiver.available

    @property
    @override
    def event_types(self) -> list[str]:
        """Return the names of the known commands."""
        return self.hass.data[DATA_COMMANDS].names()

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the known commands and the receiver."""
        await super().async_added_to_hass()
        self._receiver_key = (self.platform.platform_name, self._receiver_unique_id)
        receivers = self.hass.data.setdefault(DATA_RECEIVERS, {})
        if (receiver := receivers.get(self._receiver_key)) is not None:
            self._async_link(receiver)

        self.async_on_remove(
            self.hass.data[DATA_COMMANDS].async_add_listener(
                self._handle_commands_changed
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_INFRARED_RECEIVER_ADDED, self._handle_receiver_added
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_INFRARED_RECEIVER_REMOVED,
                self._handle_receiver_removed,
            )
        )
        self.async_on_remove(self._async_unlink)

    @callback
    def _async_link(self, receiver: InfraredReceiverEntity) -> None:
        """Start following the receiver."""
        self._receiver = receiver
        self._receiver_subscriptions = [
            receiver.async_subscribe_received_signal(self._handle_signal),
            async_track_state_change_event(
                self.hass, receiver.entity_id, self._handle_receiver_state_changed
            ),
        ]

    @callback
    def _async_unlink(self) -> None:
        """Stop following the receiver."""
        for unsubscribe in self._receiver_subscriptions:
            unsubscribe()
        self._receiver_subscriptions = []
        self._receiver = None
        self._last_received.clear()

    @callback
    def _handle_receiver_added(self, key: tuple[str, str]) -> None:
        """Link to the receiver once it is added."""
        if key != self._receiver_key or self._receiver is not None:
            return
        self._async_link(self.hass.data[DATA_RECEIVERS][key])
        self.async_write_ha_state()

    @callback
    def _handle_receiver_removed(self, key: tuple[str, str]) -> None:
        """Unlink when the receiver is removed."""
        if key != self._receiver_key:
            return
        self._async_unlink()
        self.async_write_ha_state()

    @callback
    def _handle_receiver_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Mirror the availability of the receiver."""
        if _is_available(event.data["old_state"]) != _is_available(
            event.data["new_state"]
        ):
            self.async_write_ha_state()

    @callback
    def _handle_commands_changed(self, command_id: str) -> None:
        """Report the new command names as event types."""
        self.async_write_ha_state()

    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Fire for a known command."""
        command = self.hass.data[DATA_COMMANDS].match(signal)
        if command is None:
            return
        command_id = command[CONF_ID]
        now = time.monotonic()
        previous = self._last_received.get(command_id)
        # Every repeat pushes the window out, so holding the button down fires
        # once, when it is first pressed.
        self._last_received[command_id] = now
        if previous is not None and now - previous < _REPEAT_WINDOW:
            return
        self._trigger_event(command[CONF_NAME], {"command_id": command_id})
        self.async_write_ha_state()
