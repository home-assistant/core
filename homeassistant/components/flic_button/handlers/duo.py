"""Flic Duo protocol handler implementation."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Final

from ..const import (
    COMMAND_TIMEOUT,
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_UP,
    OPCODE_BUTTON_EVENT_DUO,
    OPCODE_INIT_BUTTON_EVENTS_DUO_REQUEST,
    OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITH_BOOT_ID,
    OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITHOUT_BOOT_ID,
    OPCODE_PUSH_TWIST_DATA_NOTIFICATION,
)
from ..flic_protocol import (
    ButtonEventType,
    DuoParserState,
    EnablePushTwistRequest,
    FlicDuoEventNotification,
    Gesture,
    InitButtonEventsDuoRequest,
    PushTwistDataNotification,
)
from ..rotate_tracker import D120, RotateTracker
from .base import (
    ButtonEvent,
    DeviceCapabilities,
    RotateEvent,
    WaitForOpcodeFn,
    WaitForOpcodesFn,
    WriteGattFn,
    WritePacketFn,
)
from .flic2 import Flic2ProtocolHandler

_LOGGER = logging.getLogger(__name__)

# Rotation events arriving within this window after button DOWN are buffered.
# Swipe presses are short (~195ms); genuine push+twist holds are much longer.
ROTATION_GATE_MS: Final = 250

# After a swipe gesture is detected, suppress rotation events for this duration
# to catch trailing push_twist events from the physical dial motion.
SWIPE_SUPPRESS_MS: Final = 300


class DuoProtocolHandler(Flic2ProtocolHandler):
    """Protocol handler for Flic Duo buttons.

    Extends Flic2ProtocolHandler since Duo uses the same pairing/auth protocol
    but has different button event handling and rotation support.
    """

    _CAPABILITIES = DeviceCapabilities(
        button_count=2,
        has_rotation=True,
        has_selector=False,
        has_gestures=True,
        has_frame_header=True,
    )

    def __init__(self) -> None:
        """Initialize the Duo handler."""
        super().__init__()
        self._duo_parser_state: DuoParserState | None = None
        self._rotate_trackers: dict[int, RotateTracker] = {}
        # Rotation filtering state: suppress swipe-induced dial events
        self._button_down_time: dict[int, float] = {}
        self._swipe_suppress_until: dict[int, float] = {}
        self._rotation_buffer: dict[
            int, list[tuple[PushTwistDataNotification, float]]
        ] = {}

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        return self._CAPABILITIES

    def reset_state(self) -> None:
        """Reset handler state."""
        super().reset_state()
        self._duo_parser_state = None
        self._button_down_time.clear()
        self._swipe_suppress_until.clear()
        self._rotation_buffer.clear()

    async def init_button_events(
        self,
        connection_id: int,
        session_key: bytes | None,
        chaskey_keys: list[int] | None,
        packet_counter: int,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> int:
        """Initialize button events for Flic Duo."""
        self._connection_id = connection_id
        self._duo_parser_state = DuoParserState()
        # Duo dials: one per button, 120 degrees = 100%, clamped to 0-100
        self._rotate_trackers = {
            0: RotateTracker(  # Big button dial
                enable_backlash_suppression=True,
                full_range_units=D120,
                clamp_position=True,
            ),
            1: RotateTracker(  # Small button dial
                enable_backlash_suppression=True,
                full_range_units=D120,
                clamp_position=True,
            ),
        }

        # Initialize Duo button events
        request_msg = InitButtonEventsDuoRequest(
            connection_id=self._connection_id,
            event_count_0=0,
            event_count_1=0,
            boot_id=0,
            auto_disconnect_time=0,
            max_queued_packets=30,
            max_queued_packets_age=60,
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending InitButtonEventsDuoLightRequest (opcode=0x%02x, %d bytes)",
            OPCODE_INIT_BUTTON_EVENTS_DUO_REQUEST,
            len(request),
        )
        await write_packet(request, True)

        try:
            response = await asyncio.wait_for(
                wait_for_opcodes(
                    [
                        OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITH_BOOT_ID,
                        OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITHOUT_BOOT_ID,
                    ]
                ),
                timeout=COMMAND_TIMEOUT,
            )
            _LOGGER.debug(
                "Duo button events initialized (response: %d bytes, opcode=0x%02x)",
                len(response),
                response[1] if len(response) > 1 else -1,
            )
        except TimeoutError:
            _LOGGER.warning(
                "No response to InitButtonEventsDuoRequest, continuing anyway"
            )

        # Enable push twist (rotation) events
        await self._init_push_twist_events(write_packet)

        return packet_counter

    async def _init_push_twist_events(self, write_packet: WritePacketFn) -> None:
        """Initialize push twist (rotation) events for Flic Duo."""
        request_msg = EnablePushTwistRequest(
            connection_id=self._connection_id,
            enable_button_0=True,
            enable_button_1=True,
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending EnablePushTwistInd (opcode=0x%02x, %d bytes)",
            request[1],
            len(request),
        )
        await write_packet(request, True)
        _LOGGER.debug("Push twist events enabled")

    def handle_notification(
        self,
        data: bytes,
        connection_id: int,
    ) -> tuple[list[ButtonEvent], list[RotateEvent], int | None]:
        """Handle a notification from a Flic Duo button."""
        button_events: list[ButtonEvent] = []
        rotate_events: list[RotateEvent] = []

        if len(data) < 2:
            return button_events, rotate_events, None

        opcode = data[1]

        if opcode == OPCODE_BUTTON_EVENT_DUO:
            _LOGGER.debug(
                "Flic Duo button event packet received (opcode=0x%02x, data_len=%d)",
                opcode,
                len(data),
            )
            button_events = self._parse_duo_button_events(data[2:])
        elif opcode == OPCODE_PUSH_TWIST_DATA_NOTIFICATION:
            _LOGGER.debug(
                "Flic Duo push twist event received (opcode=0x%02x, data_len=%d)",
                opcode,
                len(data),
            )
            rotate_events = self._parse_push_twist_event(data[1:])

        return button_events, rotate_events, None

    def _parse_duo_button_events(self, event_data: bytes) -> list[ButtonEvent]:
        """Parse Flic Duo button events from notification data."""
        events: list[ButtonEvent] = []

        if self._duo_parser_state is None:
            self._duo_parser_state = DuoParserState()

        try:
            notification = FlicDuoEventNotification.from_bytes(
                event_data, self._duo_parser_state
            )
        except ValueError as err:
            _LOGGER.debug("Failed to parse Flic Duo button event: %s", err)
            if self._duo_parser_state:
                self._duo_parser_state.reset()
            return events

        if notification.has_parse_error:
            _LOGGER.warning("Duo event parsing had errors, some events may be missing")

        _LOGGER.debug(
            "Processing %d Flic Duo button events (per-button counts: %s)",
            len(notification.events),
            notification.per_button_event_count,
        )

        for idx, event in enumerate(notification.events):
            _LOGGER.debug(
                "Duo button event %d: button=%d, type=%s, timestamp_ms=%d, "
                "wasQueued=%s, gesture=%s",
                idx,
                event.button_index,
                event.event_type.name,
                event.timestamp_ms,
                event.was_queued,
                event.gesture,
            )

            # Track button press/release for rotation gating
            btn = event.button_index
            if event.event_type == ButtonEventType.DOWN:
                self._button_down_time[btn] = time.monotonic()
                self._rotation_buffer[btn] = []
            elif event.event_type in (
                ButtonEventType.UP_SIMPLE,
                ButtonEventType.UP_SINGLE_CLICK,
                ButtonEventType.UP_AFTER_HOLD,
                ButtonEventType.UP_DOUBLE_CLICK,
                ButtonEventType.UP_WITH_FLAG,
            ):
                if event.gesture is not None:
                    # Swipe detected: discard buffered rotation and suppress
                    self._swipe_suppress_until[btn] = (
                        time.monotonic() + SWIPE_SUPPRESS_MS / 1000.0
                    )
                    if btn in self._rotation_buffer:
                        _LOGGER.debug(
                            "Swipe detected on button %d, discarding %d "
                            "buffered rotation events",
                            btn,
                            len(self._rotation_buffer[btn]),
                        )
                        del self._rotation_buffer[btn]
                else:
                    # No swipe: discard buffer (events arrived during short
                    # press window but no gesture confirmed)
                    self._rotation_buffer.pop(btn, None)
                self._button_down_time.pop(btn, None)

            # Map Duo event type to HA event
            ha_event_type = self._map_duo_event_type(event.event_type)
            if ha_event_type:
                events.append(
                    ButtonEvent(
                        event_type=ha_event_type,
                        button_index=event.button_index,
                        timestamp_ms=event.timestamp_ms,
                        was_queued=event.was_queued,
                        extra_data={},
                    )
                )

            # Add gesture event if recognized
            if event.gesture is not None:
                gesture_event = self._map_gesture_to_event(event.gesture)
                if gesture_event:
                    _LOGGER.debug(
                        "Duo gesture detected: button=%d, gesture=%s -> %s",
                        event.button_index,
                        event.gesture.name,
                        gesture_event,
                    )
                    events.append(
                        ButtonEvent(
                            event_type=gesture_event,
                            button_index=event.button_index,
                            timestamp_ms=event.timestamp_ms,
                            was_queued=event.was_queued,
                            extra_data={},
                        )
                    )

        # Sync parser state for next packet
        if self._duo_parser_state and notification.events:
            last_event = notification.events[-1]
            self._duo_parser_state.initialize(
                event_counts=notification.per_button_event_count,
                last_timestamp=last_event.timestamp_ms,
                has_processed_end_of_queue_marker=(
                    notification.has_processed_end_of_queue_marker
                ),
            )

        return events

    def _map_duo_event_type(self, duo_type: ButtonEventType) -> str | None:
        """Map Flic Duo event type to Home Assistant event type."""
        match duo_type:
            case (
                ButtonEventType.UP_SIMPLE
                | ButtonEventType.UP_SINGLE_CLICK
                | ButtonEventType.UP_AFTER_HOLD
            ):
                return EVENT_TYPE_UP
            case ButtonEventType.UP_DOUBLE_CLICK | ButtonEventType.UP_WITH_FLAG:
                return EVENT_TYPE_DOUBLE_CLICK
            case ButtonEventType.DOWN:
                return EVENT_TYPE_DOWN
            case ButtonEventType.SINGLE_CLICK_TIMEOUT:
                return EVENT_TYPE_CLICK
            case ButtonEventType.HOLD:
                return EVENT_TYPE_HOLD
            case _:
                _LOGGER.debug("Unknown Duo button event type: %s", duo_type)
                return None

    def _map_gesture_to_event(self, gesture: Gesture) -> str | None:
        """Map Flic Duo gesture to Home Assistant swipe event type."""
        match gesture:
            case Gesture.LEFT:
                return EVENT_TYPE_SWIPE_LEFT
            case Gesture.RIGHT:
                return EVENT_TYPE_SWIPE_RIGHT
            case Gesture.UP:
                return EVENT_TYPE_SWIPE_UP
            case Gesture.DOWN:
                return EVENT_TYPE_SWIPE_DOWN
            case _:
                _LOGGER.debug("Unknown gesture type: %s", gesture)
                return None

    def _parse_push_twist_event(self, event_data: bytes) -> list[RotateEvent]:
        """Parse Flic Duo push twist (rotation) event.

        Returns a RotateEvent with dial_percentage (0-100) based on 120° rotation.
        Each button has its own independent dial position.

        Three-layer filtering prevents swipe gestures from triggering rotation:
        1. Zero-rotation filter: drops events with angle_diff == 0
        2. Press-duration gate: buffers events for first 250ms after button DOWN
        3. Post-swipe suppression: suppresses events for 300ms after a swipe gesture
        """
        _LOGGER.debug(
            "Processing push twist event data: %s (%d bytes)",
            event_data.hex(),
            len(event_data),
        )

        if not self._rotate_trackers:
            _LOGGER.warning(
                "Push twist event received but rotate trackers not initialized"
            )
            return []

        try:
            notification = PushTwistDataNotification.from_bytes(event_data)
        except ValueError as err:
            _LOGGER.warning("Failed to parse push twist event: %s", err)
            return []

        _LOGGER.debug(
            "Push twist parsed: buttons_pressed=%d, is_first=%d, angle_diff=%d",
            notification.buttons_pressed,
            notification.is_first_event,
            notification.angle_diff,
        )

        # Layer 1: Drop zero-rotation events
        if notification.angle_diff == 0:
            _LOGGER.debug("Dropping zero-rotation push twist event")
            return []

        # Determine which button is pressed
        # buttons_pressed: 1 = big (index 0), 2 = small (index 1), 3 = both
        button_index: int | None = None
        if notification.buttons_pressed == 1:
            button_index = 0
        elif notification.buttons_pressed == 2:
            button_index = 1
        elif notification.buttons_pressed == 3:
            button_index = 0  # Default to big when both pressed

        if button_index is None:
            return []

        now = time.monotonic()

        # Layer 3: Post-swipe suppression
        suppress_until = self._swipe_suppress_until.get(button_index, 0.0)
        if now < suppress_until:
            _LOGGER.debug(
                "Suppressing rotation for button %d (post-swipe, %.0fms remaining)",
                button_index,
                (suppress_until - now) * 1000,
            )
            return []

        # Layer 2: Press-duration gate (buffer events for first 250ms)
        down_time = self._button_down_time.get(button_index)
        if down_time is not None:
            elapsed_ms = (now - down_time) * 1000
            if elapsed_ms < ROTATION_GATE_MS:
                # Still in gate window: buffer this event
                if button_index in self._rotation_buffer:
                    self._rotation_buffer[button_index].append((notification, now))
                    _LOGGER.debug(
                        "Buffering rotation for button %d "
                        "(%.0fms since DOWN, buffer=%d)",
                        button_index,
                        elapsed_ms,
                        len(self._rotation_buffer[button_index]),
                    )
                return []

            # Gate window passed: flush any buffered events then process current
            events: list[RotateEvent] = []
            if button_index in self._rotation_buffer:
                buffered = self._rotation_buffer.pop(button_index)
                if buffered:
                    _LOGGER.debug(
                        "Gate opened for button %d, flushing %d buffered "
                        "rotation events",
                        button_index,
                        len(buffered),
                    )
                    for buffered_notif, _ in buffered:
                        event = self._emit_rotation_event(buffered_notif, button_index)
                        if event is not None:
                            events.append(event)

            event = self._emit_rotation_event(notification, button_index)
            if event is not None:
                events.append(event)
            return events

        # No active button press tracking: process normally
        event = self._emit_rotation_event(notification, button_index)
        return [event] if event is not None else []

    def _emit_rotation_event(
        self,
        notification: PushTwistDataNotification,
        button_index: int,
    ) -> RotateEvent | None:
        """Apply rotation to tracker and create a RotateEvent if significant."""
        tracker = self._rotate_trackers.get(button_index)
        if tracker is None:
            return None

        result = tracker.apply(notification.angle_diff)

        # Skip noisy events that were filtered by backlash suppression
        if result.backlash_suppressed:
            _LOGGER.debug(
                "Backlash suppressed for button %d (angle_diff=%d)",
                button_index,
                notification.angle_diff,
            )
            return None

        dial_percentage = tracker.percentage

        _LOGGER.debug(
            "Rotate tracker (button %d): dial=%.1f%%, detent_crossings=%d, rpm=%.1f",
            button_index,
            dial_percentage,
            result.detent_crossings,
            result.rpm,
        )

        # Determine event type based on direction
        event_type = (
            EVENT_TYPE_ROTATE_CLOCKWISE
            if notification.angle_diff > 0
            else EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE
        )

        return RotateEvent(
            event_type=event_type,
            button_index=button_index,
            angle_degrees=result.angle_degrees,
            detent_crossings=abs(result.detent_crossings),
            extra_data={
                "dial_percentage": dial_percentage,
                "selector_index": result.selector_index,
                "total_turns": result.total_turns,
                "total_detent_crossings": result.current_detent_crossings,
                "acceleration_multiplier": result.acceleration_multiplier,
                "rpm": result.rpm,
                "is_first_event": notification.is_first_event > 0,
            },
        )
