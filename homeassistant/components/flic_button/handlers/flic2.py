"""Flic 2 protocol handler implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import secrets
import struct
import time

from ..const import (
    COMMAND_TIMEOUT,
    FIRMWARE_FINAL_ACK_TIMEOUT,
    FIRMWARE_UPDATE_TIMEOUT,
    FLIC2_ED25519_PUBLIC_KEY,
    FLIC2_FIRMWARE_IV_SIZE,
    FLIC2_FIRMWARE_MAX_IN_FLIGHT_WORDS,
    FLIC2_FIRMWARE_WORD_CHUNK_SIZE,
    FLIC_NOTIFY_CHAR_UUID,
    FLIC_SERVICE_UUID,
    FLIC_WRITE_CHAR_UUID,
    OPCODE_BUTTON_EVENT,
    OPCODE_FIRMWARE_UPDATE_NOTIFICATION,
    OPCODE_FULL_VERIFY_REQUEST_1,
    OPCODE_FULL_VERIFY_REQUEST_2,
    OPCODE_FULL_VERIFY_RESPONSE_1,
    OPCODE_FULL_VERIFY_RESPONSE_2,
    OPCODE_GET_BATTERY_LEVEL_REQUEST,
    OPCODE_GET_BATTERY_LEVEL_RESPONSE,
    OPCODE_GET_FIRMWARE_VERSION_REQUEST,
    OPCODE_GET_FIRMWARE_VERSION_RESPONSE,
    OPCODE_GET_NAME_REQUEST,
    OPCODE_GET_NAME_RESPONSE,
    OPCODE_INIT_BUTTON_EVENTS_REQUEST,
    OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITH_BOOT_ID,
    OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITHOUT_BOOT_ID,
    OPCODE_QUICK_VERIFY_REQUEST,
    OPCODE_QUICK_VERIFY_RESPONSE,
    OPCODE_SET_NAME_REQUEST,
    OPCODE_SET_NAME_RESPONSE,
    OPCODE_START_FIRMWARE_UPDATE_RESPONSE,
    PAIRING_TIMEOUT,
)
from ..flic_protocol import (
    FirmwareUpdateNotification,
    Flic2EventNotification,
    Flic2FirmwareUpdateDataInd,
    Flic2ForceBtDisconnectInd,
    Flic2StartFirmwareUpdateRequest,
    FullVerifyResponse2,
    InitButtonEventsRequest,
    QuickVerifyRequest,
    QuickVerifyResponse,
    StartFirmwareUpdateResponse,
)
from ..flic_security import (
    chaskey_16_bytes,
    chaskey_generate_subkeys,
    derive_full_verify_keys,
    generate_x25519_keypair,
    verify_ed25519_signature_with_variant,
    x25519_key_exchange,
)
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


class Flic2ProtocolHandler(DeviceProtocolHandler):
    """Protocol handler for Flic 2 buttons (non-Duo)."""

    _CAPABILITIES = DeviceCapabilities(
        button_count=1,
        has_rotation=False,
        has_selector=False,
        has_gestures=False,
        has_frame_header=True,
    )

    def __init__(self) -> None:
        """Initialize the Flic 2 handler."""
        super().__init__()
        self._connection_id = 0

    @property
    def service_uuid(self) -> str:
        """Return the BLE service UUID."""
        return FLIC_SERVICE_UUID

    @property
    def write_char_uuid(self) -> str:
        """Return the BLE write characteristic UUID."""
        return FLIC_WRITE_CHAR_UUID

    @property
    def notify_char_uuid(self) -> str:
        """Return the BLE notify characteristic UUID."""
        return FLIC_NOTIFY_CHAR_UUID

    @property
    def ed25519_public_key(self) -> bytes:
        """Return the Ed25519 public key for signature verification."""
        return FLIC2_ED25519_PUBLIC_KEY

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        return self._CAPABILITIES

    @property
    def connection_id(self) -> int:
        """Return the current connection ID."""
        return self._connection_id

    @connection_id.setter
    def connection_id(self, value: int) -> None:
        """Set the connection ID."""
        self._connection_id = value

    async def full_verify_pairing(
        self,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> tuple[int, bytes, str, int, int, bytes, int]:
        """Perform full pairing verification for Flic 2."""
        # Generate temporary connection ID for pairing
        temp_conn_id = secrets.randbelow(2**32)
        _LOGGER.debug(
            "Starting full pairing verification with tmp_id=%d (0x%08x)",
            temp_conn_id,
            temp_conn_id,
        )

        # Step 1: Send FullVerifyRequest1
        frame_header = 0x00
        tmp_id_bytes = struct.pack("<I", temp_conn_id)
        request1 = (
            struct.pack("<BB", frame_header, OPCODE_FULL_VERIFY_REQUEST_1)
            + tmp_id_bytes
        )

        _LOGGER.debug(
            "Sending FullVerifyRequest1 (opcode=0x%02x, tmp_id=0x%08x, length=%d bytes)",
            OPCODE_FULL_VERIFY_REQUEST_1,
            temp_conn_id,
            len(request1),
        )

        await write_packet(request1, False)
        _LOGGER.debug("FullVerifyRequest1 sent, waiting for FullVerifyResponse1")

        # Wait for FullVerifyResponse1
        response1 = await asyncio.wait_for(
            wait_for_opcode(OPCODE_FULL_VERIFY_RESPONSE_1),
            timeout=PAIRING_TIMEOUT,
        )
        _LOGGER.debug("Received FullVerifyResponse1 (length=%d bytes)", len(response1))

        # Parse FullVerifyResponse1
        expected_len = 1 + 1 + 4 + 64 + 6 + 1 + 32 + 8 + 1  # 118 bytes
        if len(response1) < expected_len:
            raise ValueError(
                f"Invalid FullVerifyResponse1 length: {len(response1)} (expected {expected_len})"
            )

        offset = 2  # Skip header and opcode
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
            "Parsed FullVerifyResponse1: tmpId=0x%08x, addr=%s, addr_type=0x%02x",
            received_tmp_id,
            button_address.hex(),
            address_type,
        )

        # Extract connection ID from response header
        response_header = response1[0]
        response_conn_id = response_header & 0x1F
        response_newly_assigned = bool(response_header & 0x20)
        if response_newly_assigned:
            self._connection_id = response_conn_id
            _LOGGER.debug("Button assigned connection ID: %d", self._connection_id)

        # Verify Ed25519 signature
        signed_data = button_address + bytes([address_type]) + button_pubkey
        signature_variant = verify_ed25519_signature_with_variant(
            self.ed25519_public_key, signed_data, signature
        )
        if signature_variant is None:
            raise ValueError("Invalid button signature - all variants failed")

        _LOGGER.debug("Ed25519 signature verified with variant %d", signature_variant)

        # Generate keypair and derive keys
        app_private_key, app_public_key = generate_x25519_keypair()
        shared_secret = x25519_key_exchange(app_private_key, button_pubkey)
        client_random = secrets.token_bytes(8)

        verifier, _session_key, pairing_key, pairing_id, _ = derive_full_verify_keys(
            shared_secret,
            signature_variant,
            device_random,
            client_random,
        )

        _LOGGER.debug("Full verify keys derived (pairing_id=%d)", pairing_id)

        # Step 2: Send FullVerifyRequest2
        flags = (0 & 0x07) | (0x00 << 3) | (0 << 6) | (1 << 7)  # supportsDuo=True
        frame_header = self._connection_id & 0x1F

        request2 = (
            struct.pack("<BB", frame_header, OPCODE_FULL_VERIFY_REQUEST_2)
            + app_public_key
            + client_random
            + struct.pack("<B", flags)
            + verifier
        )

        _LOGGER.debug(
            "Sending FullVerifyRequest2 (opcode=0x%02x, conn_id=%d, length=%d bytes)",
            OPCODE_FULL_VERIFY_REQUEST_2,
            self._connection_id,
            len(request2),
        )

        await write_packet(request2, False)
        _LOGGER.debug("FullVerifyRequest2 sent, waiting for FullVerifyResponse2")

        # Wait for FullVerifyResponse2
        response2_data = await asyncio.wait_for(
            wait_for_opcode(OPCODE_FULL_VERIFY_RESPONSE_2),
            timeout=PAIRING_TIMEOUT,
        )
        _LOGGER.debug(
            "Received FullVerifyResponse2 (length=%d bytes)", len(response2_data)
        )

        # Parse FullVerifyResponse2
        response2 = FullVerifyResponse2.from_bytes(response2_data)
        serial_number = response2.serial_number

        _LOGGER.debug(
            "Button info: name=%s, serial=%s, is_duo=%s, firmware=%d",
            response2.name,
            serial_number,
            response2.is_duo,
            response2.firmware_version,
        )

        # Reset connection ID for new session
        self._connection_id = 0

        _LOGGER.info("Pairing successful (serial=%s)", serial_number)

        return (
            pairing_id,
            pairing_key,
            serial_number,
            response2.battery_level,
            0,  # sig_bits (not used for Flic 2)
            response2.button_uuid,
            response2.firmware_version,
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
        """Perform quick verification for Flic 2."""
        self._connection_id = 0

        tmp_id = secrets.randbelow(0xFFFFFFFF)
        client_random_bytes = secrets.token_bytes(7)

        request_msg = QuickVerifyRequest(
            connection_id=self._connection_id,
            tmp_id=tmp_id,
            pairing_id=pairing_id,
            client_random=client_random_bytes,
            supports_duo=True,
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending QuickVerifyRequest (opcode=0x%02x, tmp_id=0x%08x, pairing_id=0x%08x)",
            OPCODE_QUICK_VERIFY_REQUEST,
            tmp_id,
            pairing_id,
        )

        await write_packet(request, False)
        _LOGGER.debug("QuickVerifyRequest sent, waiting for QuickVerifyResponse")

        response_data = await asyncio.wait_for(
            wait_for_opcode(OPCODE_QUICK_VERIFY_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        _LOGGER.debug(
            "Received QuickVerifyResponse (length=%d bytes)", len(response_data)
        )

        response = QuickVerifyResponse.from_bytes(response_data)

        # Derive session key
        kdf_data = bytearray(16)
        kdf_data[0:7] = client_random_bytes
        kdf_data[7] = 0x40  # supportsDuo flag
        kdf_data[8:16] = response.button_random

        pairing_subkeys = chaskey_generate_subkeys(pairing_key)
        session_key = chaskey_16_bytes(pairing_subkeys, bytes(kdf_data))
        chaskey_keys = chaskey_generate_subkeys(session_key)

        _LOGGER.debug("Quick verify session key derived")

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
        """Initialize button events for Flic 2."""
        self._connection_id = connection_id

        request_msg = InitButtonEventsRequest(
            connection_id=self._connection_id,
            event_count=0,
            boot_id=0,
            auto_disconnect_time=0,
            max_queued_packets=30,
            max_queued_packets_age=60,
        )
        request = request_msg.to_bytes()

        _LOGGER.debug(
            "Sending InitButtonEventsLightRequest (opcode=0x%02x, %d bytes)",
            OPCODE_INIT_BUTTON_EVENTS_REQUEST,
            len(request),
        )

        await write_packet(request, True)

        try:
            response = await asyncio.wait_for(
                wait_for_opcodes(
                    [
                        OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITH_BOOT_ID,
                        OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITHOUT_BOOT_ID,
                    ]
                ),
                timeout=COMMAND_TIMEOUT,
            )
            _LOGGER.debug(
                "Button events initialized (response: %d bytes, opcode=0x%02x)",
                len(response),
                response[1] if len(response) > 1 else -1,
            )
        except TimeoutError:
            _LOGGER.warning("No response to InitButtonEventsRequest, continuing anyway")

    async def get_firmware_version(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the firmware version from a Flic 2/Duo device."""
        request = struct.pack(
            "<BB", connection_id & 0x1F, OPCODE_GET_FIRMWARE_VERSION_REQUEST
        )
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(OPCODE_GET_FIRMWARE_VERSION_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        return struct.unpack("<I", response[2:6])[0]

    async def get_battery_level(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the battery level from a Flic 2/Duo device."""
        request = struct.pack(
            "<BB", connection_id & 0x1F, OPCODE_GET_BATTERY_LEVEL_REQUEST
        )
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(OPCODE_GET_BATTERY_LEVEL_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        # Response: [header:1][opcode:1][battery_level:2]
        return struct.unpack("<H", response[2:4])[0]

    async def get_name(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> tuple[str, int]:
        """Request and return the device name from a Flic 2/Duo device."""
        request = struct.pack("<BB", connection_id & 0x1F, OPCODE_GET_NAME_REQUEST)
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(OPCODE_GET_NAME_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        # Response: [header:1][opcode:1][timestamp:6][name:var]
        timestamp_ms = int.from_bytes(response[2:8], "little")
        name = response[8:].decode("utf-8", errors="replace")
        return name, timestamp_ms

    async def set_name(
        self,
        connection_id: int,
        name: str,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> tuple[str, int]:
        """Set the device name on a Flic 2/Duo device."""
        name_bytes = self._truncate_name_bytes(name)

        # Build 6-byte timestamp_force: 47-bit UTC ms | force_update=1
        timestamp_ms = int(time.time() * 1000)
        # Set the force_update bit (bit 0 of the 6-byte field, highest bit)
        timestamp_force = (timestamp_ms << 1) | 1
        timestamp_force_bytes = timestamp_force.to_bytes(6, "little")

        request = (
            struct.pack("<BB", connection_id & 0x1F, OPCODE_SET_NAME_REQUEST)
            + timestamp_force_bytes
            + name_bytes
        )
        await write_packet(request, True)

        response = await asyncio.wait_for(
            wait_for_opcode(OPCODE_SET_NAME_RESPONSE),
            timeout=COMMAND_TIMEOUT,
        )
        # Response: [header:1][opcode:1][timestamp:6][name:var]
        resp_timestamp_ms = int.from_bytes(response[2:8], "little")
        resp_name = response[8:].decode("utf-8", errors="replace")
        return resp_name, resp_timestamp_ms

    def _build_firmware_start_packet(self, firmware_binary: bytes) -> bytes:
        """Build the device-specific firmware update start packet."""
        return Flic2StartFirmwareUpdateRequest.from_firmware_binary(
            firmware_binary, self._connection_id
        ).to_bytes()

    async def start_firmware_update(
        self,
        firmware_binary: bytes,
        write_packet: WritePacketFn,
        wait_for_opcodes: WaitForOpcodesFn,
    ) -> int:
        """Start a firmware update on a Flic 2/Duo device."""
        await write_packet(self._build_firmware_start_packet(firmware_binary), True)

        # Wait for either StartFirmwareUpdateResponse (18) or
        # FirmwareUpdateNotification (19).
        response_data = await asyncio.wait_for(
            wait_for_opcodes(
                [
                    OPCODE_START_FIRMWARE_UPDATE_RESPONSE,
                    OPCODE_FIRMWARE_UPDATE_NOTIFICATION,
                ]
            ),
            timeout=COMMAND_TIMEOUT,
        )

        # Strip frame header byte for parsing
        opcode = response_data[1]
        payload = response_data[1:]

        if opcode == OPCODE_FIRMWARE_UPDATE_NOTIFICATION:
            notification = FirmwareUpdateNotification.from_bytes(payload)
            _LOGGER.debug(
                "Received FirmwareUpdateNotification instead of StartResponse: pos=%d",
                notification.pos,
            )
            return notification.pos

        response = StartFirmwareUpdateResponse.from_bytes(payload)
        _LOGGER.debug("StartFirmwareUpdateResponse: start_pos=%d", response.start_pos)

        return self._validate_firmware_start_pos(response.start_pos)

    async def send_firmware_data(
        self,
        firmware_binary: bytes,
        start_pos: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Send firmware data to a Flic 2 device with word-based flow control."""
        compressed_data = firmware_binary[FLIC2_FIRMWARE_IV_SIZE:]
        total_bytes = len(compressed_data)
        total_words = total_bytes // 4

        sent_words = start_pos
        acked_words = start_pos

        _LOGGER.debug(
            "Starting Flic 2 firmware data transfer: total=%d words (%d bytes), start_pos=%d",
            total_words,
            total_bytes,
            start_pos,
        )

        while sent_words < total_words:
            # Flow control: wait if too many words in flight
            while sent_words - acked_words >= FLIC2_FIRMWARE_MAX_IN_FLIGHT_WORDS:
                notification_data = await asyncio.wait_for(
                    wait_for_opcode(OPCODE_FIRMWARE_UPDATE_NOTIFICATION),
                    timeout=FIRMWARE_UPDATE_TIMEOUT,
                )
                # Strip frame header for parsing
                notification = FirmwareUpdateNotification.from_bytes(
                    notification_data[1:]
                )

                if notification.pos == 0:
                    _LOGGER.error("Firmware signature verification failed")
                    return False

                acked_words = notification.pos
                if progress_callback:
                    # Convert words to bytes for progress
                    progress_callback(min(acked_words * 4, total_bytes), total_bytes)

                if acked_words >= total_words:
                    _LOGGER.info("Firmware transfer complete")
                    return True

            # Send next chunk of words, clamped to remaining in-flight window
            remaining_window = FLIC2_FIRMWARE_MAX_IN_FLIGHT_WORDS - (
                sent_words - acked_words
            )
            chunk_word_count = min(
                FLIC2_FIRMWARE_WORD_CHUNK_SIZE,
                total_words - sent_words,
                remaining_window,
            )
            byte_start = sent_words * 4
            byte_end = byte_start + chunk_word_count * 4
            chunk_bytes = compressed_data[byte_start:byte_end]

            # Convert bytes to word list
            words = [
                struct.unpack("<I", chunk_bytes[i : i + 4])[0]
                for i in range(0, len(chunk_bytes), 4)
            ]

            data_ind = Flic2FirmwareUpdateDataInd(
                connection_id=self._connection_id, words=words
            )
            await write_packet(data_ind.to_bytes(), True)
            sent_words += chunk_word_count

        # Wait for remaining acknowledgments.
        # After all data is sent the device verifies the signature and reboots.
        # The reboot often drops the BLE connection before the final ACK
        # arrives, so use a shorter timeout and treat it as success.
        try:
            while acked_words < total_words:
                notification_data = await asyncio.wait_for(
                    wait_for_opcode(OPCODE_FIRMWARE_UPDATE_NOTIFICATION),
                    timeout=FIRMWARE_FINAL_ACK_TIMEOUT,
                )
                notification = FirmwareUpdateNotification.from_bytes(
                    notification_data[1:]
                )

                if notification.pos == 0:
                    _LOGGER.error("Firmware signature verification failed")
                    return False

                acked_words = notification.pos
                if progress_callback:
                    progress_callback(min(acked_words * 4, total_bytes), total_bytes)
        except TimeoutError:
            _LOGGER.info(
                "Final ACK timed out after all data sent — "
                "device likely rebooted with new firmware"
            )
            return True

        _LOGGER.info("Firmware transfer complete")
        return True

    async def send_force_disconnect(
        self,
        write_packet: WritePacketFn,
        restart_adv: bool = True,
    ) -> None:
        """Send force disconnect to trigger device reboot."""
        ind = Flic2ForceBtDisconnectInd(
            connection_id=self._connection_id, restart_adv=restart_adv
        )
        await write_packet(ind.to_bytes(), True)
        _LOGGER.debug("Sent Flic2ForceBtDisconnectInd (restart_adv=%s)", restart_adv)

    def handle_notification(
        self,
        data: bytes,
        connection_id: int,
    ) -> tuple[list[ButtonEvent], list[RotateEvent], int | None]:
        """Handle a notification from a Flic 2 button."""
        button_events: list[ButtonEvent] = []
        rotate_events: list[RotateEvent] = []

        if len(data) < 2:
            return button_events, rotate_events, None

        opcode = data[1]

        if opcode == OPCODE_BUTTON_EVENT:
            _LOGGER.debug(
                "Flic 2 button event packet received (opcode=0x%02x, data_len=%d)",
                opcode,
                len(data),
            )
            button_events = self._parse_button_events(data[2:])

        return button_events, rotate_events, None

    def _parse_button_events(self, event_data: bytes) -> list[ButtonEvent]:
        """Parse Flic 2 button events from notification data."""
        events: list[ButtonEvent] = []

        try:
            notification = Flic2EventNotification.from_bytes(event_data)
        except ValueError as err:
            _LOGGER.debug("Failed to parse Flic 2 button event: %s", err)
            return events

        _LOGGER.debug(
            "Processing %d Flic 2 button events",
            len(notification.events),
        )

        for idx, event in enumerate(notification.events):
            event_name = self._get_event_name(event.event_type)
            _LOGGER.debug(
                "Button event %d: type=%d (%s), timestamp_ms=%d, "
                "wasQueued=%s, wasQueuedLast=%s",
                idx,
                event.event_type,
                event_name,
                event.timestamp_ms,
                event.was_queued,
                event.was_queued_last,
            )

            ha_event = self._map_event_type(event.event_type)
            if ha_event:
                events.append(
                    ButtonEvent(
                        event_type=ha_event,
                        button_index=None,
                        timestamp_ms=event.timestamp_ms,
                        was_queued=event.was_queued,
                        extra_data={},
                    )
                )

        return events
