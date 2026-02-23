"""Flic Twist protocol handler implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import secrets
import struct

from ..const import (
    COMMAND_TIMEOUT,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SELECTOR_CHANGED,
    FIRMWARE_DATA_CHUNK_SIZE,
    FIRMWARE_HEADER_SIZE,
    FIRMWARE_MAX_IN_FLIGHT,
    FIRMWARE_UPDATE_TIMEOUT,
    PAIRING_TIMEOUT,
    TWIST_ED25519_PUBLIC_KEY,
    TWIST_OPCODE_BUTTON_EVENT,
    TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION,
    TWIST_OPCODE_FULL_VERIFY_FAIL_RESPONSE,
    TWIST_OPCODE_FULL_VERIFY_RESPONSE_1,
    TWIST_OPCODE_FULL_VERIFY_RESPONSE_2,
    TWIST_OPCODE_GET_BATTERY_LEVEL_REQUEST,
    TWIST_OPCODE_GET_BATTERY_LEVEL_RESPONSE,
    TWIST_OPCODE_GET_FIRMWARE_VERSION_REQUEST,
    TWIST_OPCODE_GET_FIRMWARE_VERSION_RESPONSE,
    TWIST_OPCODE_INIT_BUTTON_EVENTS_RESPONSE,
    TWIST_OPCODE_QUICK_VERIFY_RESPONSE,
    TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE,
    TWIST_OPCODE_TWIST_EVENT,
    TWIST_RX_CHAR_UUID,
    TWIST_SERVICE_UUID,
    TWIST_TX_CHAR_UUID,
    PushTwistMode,
)
from ..flic_protocol import (
    FirmwareUpdateDataInd,
    FirmwareUpdateNotification,
    ForceBtDisconnectInd,
    InitButtonEventsResponseV2,
    InitButtonEventsTwistRequest,
    StartFirmwareUpdateRequest,
    StartFirmwareUpdateResponse,
    TwistButtonEventNotification,
    TwistEventNotification,
    TwistFullVerifyRequest1,
    TwistFullVerifyRequest2,
    TwistFullVerifyResponse2,
    TwistModeConfig,
    TwistQuickVerifyRequest,
    TwistQuickVerifyResponse,
    UpdateTwistPositionRequest,
)
from ..flic_security import (
    chaskey_16_bytes,
    chaskey_generate_subkeys,
    derive_full_verify_keys,
    generate_x25519_keypair,
    verify_ed25519_signature_with_variant,
    x25519_key_exchange,
)
from ..rotate_tracker import MultiModeRotateTracker
from .base import (
    ButtonEvent,
    DeviceCapabilities,
    DeviceProtocolHandler,
    RotateEvent,
    WaitForOpcodeFn,
    WaitForOpcodesFn,
    WriteGattFn,
    WritePacketFn,
)

_LOGGER = logging.getLogger(__name__)


class TwistProtocolHandler(DeviceProtocolHandler):
    """Protocol handler for Flic Twist buttons.

    Twist uses a simpler packet format than Flic 2/Duo:
    - No frame header (no connId, no fragment flags)
    - Format: [opcode:1][payload:N][mac:5 if session active]
    """

    _CAPABILITIES = DeviceCapabilities(
        button_count=1,
        has_rotation=True,
        has_selector=True,
        has_gestures=False,
        has_frame_header=False,
    )

    def __init__(self, push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT) -> None:
        """Initialize the Twist handler."""
        super().__init__()
        self._twist_mode_index: int = 0
        self._twist_packet_counter: int = 0
        self._push_twist_mode = push_twist_mode
        self._multi_mode_tracker: MultiModeRotateTracker | None = None
        self._last_event_count: int = 0
        self._last_boot_id: int = 0

    @property
    def service_uuid(self) -> str:
        """Return the BLE service UUID."""
        return TWIST_SERVICE_UUID

    @property
    def write_char_uuid(self) -> str:
        """Return the BLE write characteristic UUID."""
        return TWIST_TX_CHAR_UUID

    @property
    def notify_char_uuid(self) -> str:
        """Return the BLE notify characteristic UUID."""
        return TWIST_RX_CHAR_UUID

    @property
    def ed25519_public_key(self) -> bytes:
        """Return the Ed25519 public key for signature verification."""
        return TWIST_ED25519_PUBLIC_KEY

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        return self._CAPABILITIES

    @property
    def twist_mode_index(self) -> int:
        """Return the current twist mode index."""
        return self._twist_mode_index

    def reset_state(self) -> None:
        """Reset handler state."""
        super().reset_state()
        self._twist_mode_index = 0
        self._twist_packet_counter = 0
        self._last_event_count = 0
        self._last_boot_id = 0

    async def full_verify_pairing(
        self,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> tuple[int, bytes, str, int, int, bytes]:
        """Perform full pairing verification for Flic Twist."""
        temp_conn_id = secrets.randbelow(2**32)
        _LOGGER.debug(
            "Starting Twist full pairing with tmp_id=%d (0x%08x)",
            temp_conn_id,
            temp_conn_id,
        )

        # Twist uses no frame header - just opcode + data
        request1 = TwistFullVerifyRequest1(tmp_id=temp_conn_id).to_bytes()
        _LOGGER.debug(
            "Sending TwistFullVerifyRequest1 (length=%d bytes)", len(request1)
        )

        await write_gatt(self.write_char_uuid, request1)
        _LOGGER.debug("TwistFullVerifyRequest1 sent, waiting for response")

        response1 = await asyncio.wait_for(
            wait_for_opcode(TWIST_OPCODE_FULL_VERIFY_RESPONSE_1),
            timeout=PAIRING_TIMEOUT,
        )
        _LOGGER.debug(
            "Received TwistFullVerifyResponse1 (length=%d bytes)",
            len(response1),
        )

        # Parse Twist response (no frame header)
        expected_len = 1 + 4 + 64 + 6 + 1 + 32 + 8 + 1  # 117 bytes
        if len(response1) < expected_len:
            raise ValueError(
                f"Invalid TwistFullVerifyResponse1 length: {len(response1)} (expected {expected_len})"
            )

        offset = 1  # Skip opcode only
        received_tmp_id = struct.unpack("<I", response1[offset : offset + 4])[0]
        offset += 4

        if received_tmp_id != temp_conn_id:
            raise ValueError(
                f"tmpId mismatch: expected {temp_conn_id}, got {received_tmp_id}"
            )

        signature = response1[offset : offset + 64]
        offset += 64
        button_address = response1[offset : offset + 6]
        offset += 6
        address_type = response1[offset]
        offset += 1
        button_pubkey = response1[offset : offset + 32]
        offset += 32
        device_random = response1[offset : offset + 8]

        _LOGGER.debug(
            "Parsed TwistFullVerifyResponse1: tmpId=0x%08x, addr=%s, addr_type=0x%02x",
            received_tmp_id,
            button_address.hex(),
            address_type,
        )
        # Verify Ed25519 signature
        signed_data = button_address + bytes([address_type]) + button_pubkey
        signature_variant = verify_ed25519_signature_with_variant(
            self.ed25519_public_key, signed_data, signature
        )
        if signature_variant is None:
            _LOGGER.error("Ed25519 verification failed for all variants")
            raise ValueError("Invalid Twist signature - all variants failed")

        _LOGGER.debug(
            "Twist Ed25519 signature verified with sigBits=%d",
            signature_variant,
        )

        # Generate keypair and derive keys
        app_private_key, app_public_key = generate_x25519_keypair()
        shared_secret = x25519_key_exchange(app_private_key, button_pubkey)
        client_random = secrets.token_bytes(8)

        verifier, _session_key, pairing_key, pairing_id, _full_verify_secret = (
            derive_full_verify_keys(
                shared_secret,
                signature_variant,
                device_random,
                client_random,
                is_twist=True,
            )
        )

        _LOGGER.debug("Key derivation complete (pairing_id=%d)", pairing_id)

        # Step 2: Send FullVerifyRequest2
        # NOTE: The signature_variant in the request is ALWAYS 0 for Twist.
        # The sigBits from Ed25519 verification is only used for key derivation,
        # not in the request flags. This matches the official Twist SDK behavior.
        request2 = TwistFullVerifyRequest2(
            ecdh_public_key=app_public_key,
            client_random=client_random,
            signature_variant=0,  # Always 0 for Twist (per SDK)
            verifier=verifier,
        ).to_bytes()

        _LOGGER.debug(
            "Sending TwistFullVerifyRequest2 (%d bytes)",
            len(request2),
        )
        await write_gatt(self.write_char_uuid, request2)

        # Wait for response
        response2_data = await asyncio.wait_for(
            wait_for_opcodes(
                [
                    TWIST_OPCODE_FULL_VERIFY_RESPONSE_2,
                    TWIST_OPCODE_FULL_VERIFY_FAIL_RESPONSE,
                ]
            ),
            timeout=PAIRING_TIMEOUT,
        )
        _LOGGER.debug(
            "Received Twist response (opcode=0x%02x, length=%d bytes)",
            response2_data[0] if response2_data else -1,
            len(response2_data),
        )

        if response2_data[0] == TWIST_OPCODE_FULL_VERIFY_FAIL_RESPONSE:
            reason = response2_data[1] if len(response2_data) > 1 else 0
            reason_str = {0: "INVALID_VERIFIER", 1: "NOT_IN_PUBLIC_MODE"}.get(
                reason, f"UNKNOWN({reason})"
            )
            raise ValueError(f"Twist pairing failed: {reason_str} (code {reason})")

        response2 = TwistFullVerifyResponse2.from_bytes(response2_data)

        _LOGGER.info("Twist paired (serial=%s)", response2.serial_number)

        return (
            pairing_id,
            pairing_key,
            response2.serial_number,
            response2.battery_level,
            signature_variant,
            response2.button_uuid,
        )

    async def quick_verify(
        self,
        pairing_id: int,
        pairing_key: bytes,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        write_packet: WritePacketFn,
        sig_bits: int = 0,
    ) -> tuple[bytes, list[int]]:
        """Perform quick verification for Flic Twist."""
        tmp_id = secrets.randbelow(0xFFFFFFFF)
        client_random_bytes = secrets.token_bytes(7)

        # Twist SDK always uses signatureVariant=0 and encryptionVariant=0 for quick verify
        # (unlike Flic 2 which uses stored sig_bits)
        request_msg = TwistQuickVerifyRequest(
            tmp_id=tmp_id,
            pairing_id=pairing_id,
            client_random=client_random_bytes,
            signature_variant=0,  # Always 0 for Twist (per SDK)
            encryption_variant=0,  # No encryption
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending TwistQuickVerifyRequest (tmp_id=0x%08x, pairing_id=0x%08x, length=%d bytes)",
            tmp_id,
            pairing_id,
            len(request),
        )

        await write_gatt(self.write_char_uuid, request)
        _LOGGER.debug("TwistQuickVerifyRequest sent, waiting for response")

        response_data = await asyncio.wait_for(
            wait_for_opcode(TWIST_OPCODE_QUICK_VERIFY_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        _LOGGER.debug(
            "Received TwistQuickVerifyResponse (length=%d bytes)",
            len(response_data),
        )

        response = TwistQuickVerifyResponse.from_bytes(response_data)

        # Derive session key (Twist: no supportsDuo flag)
        kdf_data = bytearray(16)
        kdf_data[0:7] = client_random_bytes
        kdf_data[7] = 0x00  # No supportsDuo flag for Twist
        kdf_data[8:16] = response.button_random

        _LOGGER.debug("Twist QuickVerify KDF data: %s", bytes(kdf_data).hex())

        pairing_subkeys = chaskey_generate_subkeys(pairing_key)
        session_key = chaskey_16_bytes(pairing_subkeys, bytes(kdf_data))
        chaskey_keys = chaskey_generate_subkeys(session_key)

        _LOGGER.debug("Twist quick verify session key derived")

        return session_key, chaskey_keys

    async def init_button_events(
        self,
        connection_id: int,
        session_key: bytes | None,
        chaskey_keys: list[int] | None,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> None:
        """Initialize button events for Flic Twist."""
        self._multi_mode_tracker = MultiModeRotateTracker()

        # Build 13 mode configs based on push_twist_mode setting
        mode_configs = []

        if self._push_twist_mode == PushTwistMode.SELECTOR:
            # Selector mode: enable click events and slots functionality
            for i in range(13):
                if i == 12:
                    config = TwistModeConfig(
                        led_mode=3,  # SDK default
                        has_click=False,
                        has_double_click=False,
                        extra_leds_after=0,
                        position=0,
                        timeout_seconds=0,
                    )
                else:
                    config = TwistModeConfig(
                        led_mode=1,  # SDK default
                        has_click=True,
                        has_double_click=True,
                        extra_leds_after=0,
                        position=0,
                        timeout_seconds=60,
                    )
                mode_configs.append(config)
        else:
            # Default mode: basic rotation without click events
            for _ in range(13):
                config = TwistModeConfig(
                    led_mode=1,  # SDK default
                    has_click=False,
                    has_double_click=False,
                    extra_leds_after=0,
                    position=0,
                    timeout_seconds=0,
                )
                mode_configs.append(config)

        request_msg = InitButtonEventsTwistRequest(
            mode_configs=mode_configs,
            event_count=self._last_event_count,
            boot_id=self._last_boot_id,
            api_version=2,
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending InitButtonEventsTwistRequest (%d bytes)",
            len(request),
        )

        authenticated = session_key is not None and chaskey_keys is not None
        await write_packet(request, authenticated)

        try:
            response = await asyncio.wait_for(
                wait_for_opcode(TWIST_OPCODE_INIT_BUTTON_EVENTS_RESPONSE),
                timeout=COMMAND_TIMEOUT,
            )

            try:
                init_response = InitButtonEventsResponseV2.from_bytes(response)
                self._last_event_count = init_response.event_count
                self._last_boot_id = init_response.boot_id
                _LOGGER.debug(
                    "Twist button events initialized: has_queued=%s, "
                    "event_count=%d, boot_id=%d, api_version=%d",
                    init_response.has_queued_events,
                    init_response.event_count,
                    init_response.boot_id,
                    init_response.api_version,
                )
            except ValueError as err:
                _LOGGER.debug(
                    "Could not parse InitButtonEventsResponse (%d bytes): %s",
                    len(response),
                    err,
                )
        except TimeoutError:
            _LOGGER.warning(
                "No response to InitButtonEventsTwistRequest, continuing anyway"
            )

    async def get_firmware_version(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the firmware version from a Flic Twist device."""
        request = struct.pack("<B", TWIST_OPCODE_GET_FIRMWARE_VERSION_REQUEST)
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(TWIST_OPCODE_GET_FIRMWARE_VERSION_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        return struct.unpack("<I", response[1:5])[0]

    async def get_battery_level(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the battery level from a Flic Twist device."""
        request = struct.pack("<B", TWIST_OPCODE_GET_BATTERY_LEVEL_REQUEST)
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(TWIST_OPCODE_GET_BATTERY_LEVEL_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        # Response: [opcode:1][battery_level:2]
        return struct.unpack("<H", response[1:3])[0]

    def handle_notification(
        self,
        data: bytes,
        connection_id: int,
    ) -> tuple[list[ButtonEvent], list[RotateEvent], int | None]:
        """Handle a notification from a Flic Twist button.

        Twist notifications have opcode as the first byte (no frame header).
        """
        button_events: list[ButtonEvent] = []
        rotate_events: list[RotateEvent] = []
        selector_change: int | None = None

        if len(data) < 1:
            return button_events, rotate_events, selector_change

        opcode = data[0]

        if opcode == TWIST_OPCODE_BUTTON_EVENT:
            _LOGGER.debug(
                "Twist button event received (opcode=0x%02x, data_len=%d)",
                opcode,
                len(data),
            )
            button_events, selector_change = self._parse_twist_button_events(data)
        elif opcode == TWIST_OPCODE_TWIST_EVENT:
            _LOGGER.debug(
                "Twist rotation event received (opcode=0x%02x, data_len=%d)",
                opcode,
                len(data),
            )
            rotate_events = self._parse_twist_rotation_event(data)

        return button_events, rotate_events, selector_change

    def _parse_twist_button_events(
        self, event_data: bytes
    ) -> tuple[list[ButtonEvent], int | None]:
        """Parse Twist button events from notification data."""
        events: list[ButtonEvent] = []
        selector_change: int | None = None

        try:
            notification = TwistButtonEventNotification.from_bytes(event_data[1:])
        except ValueError as err:
            _LOGGER.debug("Failed to parse Twist button event: %s", err)
            return events, selector_change

        _LOGGER.debug(
            "Processing %d Twist button events",
            len(notification.events),
        )

        for idx, event in enumerate(notification.events):
            event_name = self._get_event_name(event.event_type)
            _LOGGER.debug(
                "Twist button event %d: type=%d (%s), mode=%d, timestamp_ms=%d, "
                "wasQueued=%s",
                idx,
                event.event_type,
                event_name,
                event.twist_mode_index,
                event.timestamp_ms,
                event.was_queued,
            )

            # Track mode changes (selector position)
            if event.twist_mode_index != self._twist_mode_index:
                old_mode = self._twist_mode_index
                self._twist_mode_index = event.twist_mode_index
                _LOGGER.debug(
                    "Twist mode changed: %d -> %d",
                    old_mode,
                    event.twist_mode_index,
                )

                # Emit selector change event for slot modes (0-11)
                if event.twist_mode_index < 12:
                    events.append(
                        ButtonEvent(
                            event_type=EVENT_TYPE_SELECTOR_CHANGED,
                            button_index=None,
                            timestamp_ms=event.timestamp_ms,
                            was_queued=event.was_queued,
                            extra_data={
                                "selector_index": event.twist_mode_index,
                                "previous_index": old_mode,
                                "twist_mode_index": event.twist_mode_index,
                            },
                        )
                    )
                    selector_change = event.twist_mode_index

            # Map event type to HA event
            ha_event = self._map_event_type(event.event_type)
            if ha_event:
                events.append(
                    ButtonEvent(
                        event_type=ha_event,
                        button_index=None,
                        timestamp_ms=event.timestamp_ms,
                        was_queued=event.was_queued,
                        extra_data={"twist_mode_index": event.twist_mode_index},
                    )
                )

        return events, selector_change

    def build_update_twist_position(
        self, mode_index: int, desired_position: int
    ) -> bytes:
        """Build an UpdateTwistPositionRequest.

        The device displays position as (absolute_position - min).
        To make it show desired_position, we set:
            new_min = absolute_position - desired_position

        Args:
            mode_index: Twist mode index (0-11 for slots)
            desired_position: Desired display position in raw units (0-49152)

        Returns:
            Serialized request bytes ready for _write_packet

        """
        absolute_position = 0
        if self._multi_mode_tracker is not None:
            absolute_position = self._multi_mode_tracker.get_absolute_position(
                mode_index
            )

        new_min = absolute_position - desired_position

        if self._multi_mode_tracker is not None:
            # Update local min to match what the device will have
            self._multi_mode_tracker.set_mode_min(mode_index, new_min)

        request = UpdateTwistPositionRequest(
            twist_mode_index=mode_index,
            new_min=new_min,
            num_received_update_packets=self._twist_packet_counter,
        )
        return request.to_bytes()

    async def start_firmware_update(
        self,
        firmware_binary: bytes,
        write_packet: WritePacketFn,
        wait_for_opcodes: WaitForOpcodesFn,
    ) -> int:
        """Start a firmware update on the device.

        Args:
            firmware_binary: Raw firmware binary (header + compressed data)
            write_packet: Function to write authenticated packets
            wait_for_opcodes: Function to wait for one of several opcodes

        Returns:
            start_pos from device (0=new, >0=resume position)

        Raises:
            ValueError: If device returns an error code

        """
        request = StartFirmwareUpdateRequest.from_firmware_binary(firmware_binary)
        await write_packet(request.to_bytes(), True)

        # Wait for either StartFirmwareUpdateResponse (0x0E) or
        # FirmwareUpdateNotification (0x0F). The device may send 0x0F
        # immediately if resuming a previous transfer.
        response_data = await asyncio.wait_for(
            wait_for_opcodes(
                [
                    TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE,
                    TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION,
                ]
            ),
            timeout=COMMAND_TIMEOUT,
        )

        opcode = response_data[0]
        if opcode == TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION:
            # Device is already sending progress from a previous/resumed transfer
            notification = FirmwareUpdateNotification.from_bytes(response_data)
            _LOGGER.debug(
                "Received FirmwareUpdateNotification instead of StartResponse: pos=%d",
                notification.pos,
            )
            return notification.pos

        response = StartFirmwareUpdateResponse.from_bytes(response_data)

        _LOGGER.debug("StartFirmwareUpdateResponse: start_pos=%d", response.start_pos)

        if response.start_pos == -1:
            raise ValueError("Device rejected firmware update: invalid parameters")
        if response.start_pos == -2:
            raise ValueError("Device rejected firmware update: device busy")
        if response.start_pos == -3:
            raise ValueError(
                "Device rejected firmware update: pending reboot from previous update"
            )

        return response.start_pos

    async def send_firmware_data(
        self,
        firmware_binary: bytes,
        start_pos: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Send firmware data chunks to the device with flow control.

        Args:
            firmware_binary: Raw firmware binary (header + compressed data)
            start_pos: Byte position to start/resume from
            write_packet: Function to write authenticated packets
            wait_for_opcode: Function to wait for a specific opcode
            progress_callback: Called with (bytes_acked, total_bytes)

        Returns:
            True on success, False on signature verification failure

        """
        compressed_data = firmware_binary[FIRMWARE_HEADER_SIZE:]
        total_bytes = len(compressed_data)
        sent_pos = start_pos
        acked_pos = start_pos

        _LOGGER.debug(
            "Starting firmware data transfer: total=%d bytes, start_pos=%d",
            total_bytes,
            start_pos,
        )

        while sent_pos < total_bytes:
            # Flow control: wait if too many bytes in flight
            while sent_pos - acked_pos >= FIRMWARE_MAX_IN_FLIGHT:
                notification_data = await asyncio.wait_for(
                    wait_for_opcode(TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION),
                    timeout=FIRMWARE_UPDATE_TIMEOUT,
                )
                notification = FirmwareUpdateNotification.from_bytes(notification_data)

                if notification.pos == 0:
                    _LOGGER.error("Firmware signature verification failed")
                    return False

                acked_pos = notification.pos
                if progress_callback:
                    progress_callback(acked_pos, total_bytes)

                if acked_pos >= total_bytes:
                    _LOGGER.info("Firmware transfer complete")
                    return True

            # Send next chunk
            chunk_end = min(sent_pos + FIRMWARE_DATA_CHUNK_SIZE, total_bytes)
            chunk = compressed_data[sent_pos:chunk_end]

            data_ind = FirmwareUpdateDataInd(chunk_data=chunk)
            await write_packet(data_ind.to_bytes(), True)
            sent_pos = chunk_end

        # Wait for remaining acknowledgments
        while acked_pos < total_bytes:
            notification_data = await asyncio.wait_for(
                wait_for_opcode(TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION),
                timeout=FIRMWARE_UPDATE_TIMEOUT,
            )
            notification = FirmwareUpdateNotification.from_bytes(notification_data)

            if notification.pos == 0:
                _LOGGER.error("Firmware signature verification failed")
                return False

            acked_pos = notification.pos
            if progress_callback:
                progress_callback(acked_pos, total_bytes)

        _LOGGER.info("Firmware transfer complete")
        return True

    async def send_force_disconnect(
        self,
        write_packet: WritePacketFn,
        restart_adv: bool = True,
    ) -> None:
        """Send force disconnect to trigger device reboot.

        Args:
            write_packet: Function to write authenticated packets
            restart_adv: Whether device should restart advertising after reboot

        """
        ind = ForceBtDisconnectInd(restart_adv=restart_adv)
        await write_packet(ind.to_bytes(), True)
        _LOGGER.debug("Sent ForceBtDisconnectInd (restart_adv=%s)", restart_adv)

    def _parse_twist_rotation_event(self, event_data: bytes) -> list[RotateEvent]:
        """Parse Twist rotation event."""
        events: list[RotateEvent] = []

        if self._multi_mode_tracker is None:
            _LOGGER.warning(
                "Twist rotation event received but rotate tracker not initialized"
            )
            return events

        try:
            notification = TwistEventNotification.from_bytes(event_data)
        except ValueError as err:
            _LOGGER.warning("Failed to parse Twist rotation event: %s", err)
            return events

        _LOGGER.debug(
            "TwistEventNotification: mode_index=%d, total_delta=%d, "
            "min_delta=%d, max_delta=%d, hub_counter=%d, "
            "min_update_was_top=%s, hub_update_too_old=%s",
            notification.twist_mode_index,
            notification.total_delta,
            notification.min_delta,
            notification.max_delta,
            notification.last_hub_packet_counter,
            notification.last_min_update_was_top,
            notification.last_hub_update_packet_too_old,
        )

        self._twist_packet_counter += 1

        # Apply rotation to the specific mode's tracker
        result = self._multi_mode_tracker.apply(
            notification.twist_mode_index,
            notification.total_delta,
            notification.min_delta,
            notification.max_delta,
            notification.last_min_update_was_top,
        )

        # Get mode percentage for slot entity updates
        mode_percentage = self._multi_mode_tracker.get_mode_percentage(
            notification.twist_mode_index
        )

        _LOGGER.debug(
            "Twist rotate result: detent_crossings=%d, angle=%.1f, rpm=%.1f, mode_pct=%.1f",
            result.detent_crossings,
            result.angle_degrees,
            result.rpm,
            mode_percentage,
        )

        if result.detent_crossings != 0:
            event_type = (
                EVENT_TYPE_ROTATE_CLOCKWISE
                if result.detent_crossings > 0
                else EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE
            )

            _LOGGER.debug(
                "Emitting Twist rotate event: %s, mode=%d, detents=%d, angle=%.1f",
                event_type,
                notification.twist_mode_index,
                result.detent_crossings,
                result.angle_degrees,
            )

            events.append(
                RotateEvent(
                    event_type=event_type,
                    button_index=None,
                    angle_degrees=result.angle_degrees,
                    detent_crossings=abs(result.detent_crossings),
                    extra_data={
                        "selector_index": result.selector_index,
                        "total_turns": result.total_turns,
                        "total_detent_crossings": result.current_detent_crossings,
                        "acceleration_multiplier": result.acceleration_multiplier,
                        "rpm": result.rpm,
                        "twist_mode_index": notification.twist_mode_index,
                        "mode_percentage": mode_percentage,
                    },
                )
            )

        return events
