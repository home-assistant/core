"""Event handling for the Matrix component."""

from __future__ import annotations

import logging

from nio import (
    AsyncClient,
    Event,
    KeyVerificationCancel,
    KeyVerificationKey,
    KeyVerificationMac,
    KeyVerificationStart,
    MatrixRoom,
    MegolmEvent,
)
from nio.events.room_events import RoomMessageText
from nio.events.to_device import KeyVerificationEvent
from nio.exceptions import LocalProtocolError
from nio.responses import ToDeviceError

from homeassistant.core import HomeAssistant

from .types import ConfigCommand, RoomID, WordCommand

_LOGGER = logging.getLogger(__name__)

EVENT_MATRIX_COMMAND = "matrix_command"


class MatrixEvents:
    """Handle Matrix events and commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        mx_id: str,
        client: AsyncClient,
        word_commands: dict[RoomID, dict[WordCommand, ConfigCommand]],
        expression_commands: dict[RoomID, list[ConfigCommand]],
        listening_rooms: dict,
    ) -> None:
        """Initialize event handler."""
        self.hass = hass
        self._mx_id = mx_id
        self._client = client
        self._word_commands = word_commands
        self._expression_commands = expression_commands
        self._listening_rooms = listening_rooms

    async def handle_room_message(self, room: MatrixRoom, message: Event) -> None:
        """Handle a message sent to a Matrix room."""
        # Corresponds to message type 'm.text' and NOT other RoomMessage subtypes, like 'm.notice' and 'm.emote'.
        if not isinstance(message, RoomMessageText):
            return
        # Don't respond to our own messages.
        if message.sender == self._mx_id:
            return
        _LOGGER.debug("Handling message: %s", message.body)

        room_id = RoomID(room.room_id)

        if message.body.startswith("!"):
            # Could trigger a single-word command.
            pieces = message.body.split()
            word = WordCommand(pieces[0].lstrip("!"))

            if command := self._word_commands.get(room_id, {}).get(word):
                message_data = {
                    "command": command["name"],
                    "sender": message.sender,
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, message_data)

        # After single-word commands, check all regex commands in the room.
        for command in self._expression_commands.get(room_id, []):
            match = command["expression"].match(message.body)
            if not match:
                continue
            message_data = {
                "command": command["name"],
                "sender": message.sender,
                "room": room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, message_data)

    def load_commands(
        self, commands: list[ConfigCommand], listening_rooms: dict
    ) -> None:
        """Load and organize commands."""
        for command in commands:
            # Set the command for all listening_rooms, unless otherwise specified.
            if rooms := command.get("rooms"):
                command["rooms"] = [listening_rooms[room] for room in rooms]
            else:
                command["rooms"] = list(listening_rooms.values())

            # COMMAND_SCHEMA guarantees that exactly one of CONF_WORD and CONF_EXPRESSION are set.
            if (word_command := command.get("word")) is not None:
                for room_id in command["rooms"]:
                    self._word_commands.setdefault(room_id, {})
                    self._word_commands[room_id][word_command] = command
            else:
                for room_id in command["rooms"]:
                    self._expression_commands.setdefault(room_id, [])
                    self._expression_commands[room_id].append(command)

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """Handle decryption failure events for configured rooms only."""
        if not isinstance(event, MegolmEvent):
            return

        # Only process decryption failures for rooms we're listening to
        room_id = RoomID(room.room_id)
        if room_id not in self._listening_rooms.values():
            _LOGGER.debug(
                "Ignoring decryption failure for unconfigured room: %s", room.room_id
            )
            return

        _LOGGER.error(
            "Failed to decrypt message: %s from %s in %s. "
            "If this error persists despite verification, reset the crypto session by deleting "
            "the .matrix_store directory. You will have to verify any verified devices anew",
            event.event_id,
            event.sender,
            room.room_id,
        )

        # Send a notice message to the room
        await self._client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.notice",
                "body": "Failed to decrypt your message. "
                "Make sure encryption is enabled in my config and "
                "either enable sending messages to unverified devices or verify me if possible",
            },
        )

    async def emoji_verification(self, event: KeyVerificationEvent) -> None:
        """Callback for handling interactive verification using emoji.

        Adapted from matrix-nio examples for Home Assistant use.

        Parameters
        ----------
        event : nio.events.to_device.KeyVerificationEvent

        """
        try:
            if isinstance(event, KeyVerificationStart):
                # First step: receive m.key.verification.start
                if "emoji" not in event.short_authentication_string:
                    _LOGGER.warning(
                        "Other device does not support emoji verification %s",
                        event.short_authentication_string,
                    )
                    return

                # Send m.key.verification.accept
                resp = await self._client.accept_key_verification(event.transaction_id)
                if isinstance(resp, ToDeviceError):
                    _LOGGER.error(
                        "Call to accept_key_verification failed with %s", resp
                    )

                sas = self._client.key_verifications[event.transaction_id]

                # Send m.key.verification.key
                todevice_msg = sas.share_key()
                resp = await self._client.to_device(todevice_msg)
                if isinstance(resp, ToDeviceError):
                    _LOGGER.error("Call to to_device failed with %s", resp)

            elif isinstance(event, KeyVerificationCancel):
                # Anytime: verification cancelled
                _LOGGER.info(
                    'Verification has been cancelled by %s for reason "%s"',
                    event.sender,
                    event.reason,
                )

            elif isinstance(event, KeyVerificationKey):
                # Second step: receive m.key.verification.key
                sas = self._client.key_verifications[event.transaction_id]
                emoji = sas.get_emoji()

                _LOGGER.info("Emoji verification request: %s", emoji)

                # For Home Assistant, we'll auto-accept emoji verification
                # In a real implementation, you might want to store this
                # and allow manual verification through the UI
                _LOGGER.info("Auto-accepting emoji verification")

                # Send m.key.verification.mac
                resp = await self._client.confirm_short_auth_string(
                    event.transaction_id
                )
                if isinstance(resp, ToDeviceError):
                    _LOGGER.error(
                        "Call to confirm_short_auth_string failed with %s", resp
                    )

            elif isinstance(event, KeyVerificationMac):
                # Third step: receive m.key.verification.mac
                sas = self._client.key_verifications[event.transaction_id]
                try:
                    todevice_msg = sas.get_mac()
                except LocalProtocolError as e:
                    _LOGGER.error(
                        "Cancelled or protocol error: Reason: %s. "
                        "Verification with %s not concluded. Try again?",
                        e,
                        event.sender,
                    )
                else:
                    # Send m.key.verification.mac
                    resp = await self._client.to_device(todevice_msg)
                    if isinstance(resp, ToDeviceError):
                        _LOGGER.error("Call to to_device failed with %s", resp)

                    _LOGGER.debug(
                        "SAS status: we_started_it=%s, sas_accepted=%s, "
                        "canceled=%s, timed_out=%s, verified=%s, "
                        "verified_devices=%s",
                        sas.we_started_it,
                        sas.sas_accepted,
                        sas.canceled,
                        sas.timed_out,
                        sas.verified,
                        sas.verified_devices,
                    )
                    _LOGGER.info("Emoji verification was successful!")
            else:
                _LOGGER.warning(
                    "Received unexpected event type %s. Event is %s. Event will be ignored",
                    type(event),
                    event,
                )

        except Exception:
            _LOGGER.exception("Error in emoji verification")
