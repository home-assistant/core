"""Tonewinner AT-500 media player."""

import asyncio
import contextlib
import logging

import serial
import serial_asyncio_fast
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, CONF_SOURCE_MAPPINGS, DOMAIN
from .protocol import TonewinnerCommands, TonewinnerProtocol

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Tonewinner media_player module loaded!")


class TonewinnerError(Exception):
    """Exception for Tonewinner errors."""


# Map source names to command suffixes
INPUT_SOURCES = {
    "HDMI 1": "HD1",
    "HDMI 2": "HD2",
    "HDMI 3": "HD3",
    "HDMI 4": "HD4",
    "HDMI 5": "HD5",
    "HDMI 6": "HD6",
    "Optical 1": "OP1",
    "Optical 2": "OP2",
    "Coaxial 1": "CO1",
    "Coaxial 2": "CO2",
    "Analog 1": "AN1",
    "Analog 2": "AN2",
    "Analog 3": "AN3",
    "Bluetooth": "BT",
    "USB": "USB",
    "PC": "PC",
    "HDMI eARC": "ARC",
}

# Map sound mode names to command codes
SOUND_MODES = {mode.label: mode.command for mode in TonewinnerCommands.MODES.values()}


# Service registration schema
SERVICE_SEND_RAW = "send_raw"
SERVICE_SEND_RAW_SCHEMA = vol.Schema(
    {
        vol.Required("command"): cv.string,
    }
)

SERIAL_CONFIG = {
    "baudrate": 9600,
    "bytesize": serial.EIGHTBITS,  # 8-bit data
    "parity": serial.PARITY_NONE,  # -parenb: no parity
    "stopbits": serial.STOPBITS_ONE,  # -cstopb: 1 stop bit
    "timeout": 1.0,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media player and register service."""
    _LOGGER.debug("Setting up Tonewinner media player platform")
    _LOGGER.debug("Config entry ID: %s", config_entry.entry_id)

    # Create the entity
    data = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Creating TonewinnerMediaPlayer entity with data: %s", data)
    entity = TonewinnerMediaPlayer(hass, config_entry, data)
    async_add_entities([entity])
    _LOGGER.debug("Entity added successfully")

    # Register the service HERE – hass is available in this function
    async def handle_send_raw(call: ServiceCall):
        command = call.data["command"]
        _LOGGER.debug("send_raw service called with command: %s", command)
        await entity.send_raw_command(command)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_RAW, handle_send_raw, schema=SERVICE_SEND_RAW_SCHEMA
    )
    _LOGGER.debug("Registered send_raw service")

    # Store handle for cleanup
    hass.data[DOMAIN][f"{config_entry.entry_id}_service"] = handle_send_raw
    _LOGGER.info("Tonewinner media player platform setup complete")


class TonewinnerSerialProtocol(asyncio.Protocol):
    """Tonewinner AT-500 protocol implementation."""

    def __init__(self, entity) -> None:
        """Initialize TonewinnerProtocol."""
        self.entity = entity
        self.transport = None
        self.buffer = b""

    def connection_made(self, transport) -> None:
        """Connection made."""
        self.transport = transport
        _LOGGER.debug("Connection established successfully")
        self.entity.set_available(True)

    def data_received(self, data) -> None:
        """Data received."""
        _LOGGER.debug("Raw RX data: %s", data.hex())
        self.buffer += data
        _LOGGER.debug("Buffer state: %s", self.buffer.hex())

        # Parse ToneWinner protocol: messages start with '#' and end with '*'
        # with no newlines. Messages may arrive in multiple chunks.
        while True:
            # Find start of next message
            start_idx = self.buffer.find(b"#")
            if start_idx == -1:
                # No start marker in buffer, clear it
                _LOGGER.debug(
                    "No start marker found, clearing buffer (existing buffer: %s)",
                    self.buffer.hex(),
                )
                self.buffer = b""
                break

            # Find end of message
            end_idx = self.buffer.find(b"*", start_idx)
            if end_idx == -1:
                # Incomplete message (no end marker), keep data from '#'
                _LOGGER.debug("Incomplete message, waiting for end marker")
                self.buffer = self.buffer[start_idx:]
                break

            # Extract message content (between # and *)
            message = self.buffer[start_idx + 1 : end_idx]
            if message:
                self.entity.handle_response(message.decode("ascii", errors="ignore"))

            # Remove processed message from buffer
            self.buffer = self.buffer[end_idx + 1 :]

    def connection_lost(self, exc) -> None:
        """Connection lost."""
        _LOGGER.debug("Connection lost: %s", exc)
        self.entity.set_available(False)


class TonewinnerMediaPlayer(MediaPlayerEntity):
    """Tonewinner AT-500 media player."""

    _transport: None | serial_asyncio_fast.SerialTransport
    _protocol: None | asyncio.Protocol
    _source_check_task: None | asyncio.Task[None]

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, hass, entry, data):
        """Initialize the media player."""
        _LOGGER.info("Initializing TonewinnerMediaPlayer for entry: %s", entry.entry_id)
        _LOGGER.debug("Entry data: %s", entry.data)
        _LOGGER.debug("Entry options: %s", entry.options)
        self.hass = hass
        self.port = data[CONF_SERIAL_PORT]
        self.baud = data.get(CONF_BAUD_RATE, 9600)
        _LOGGER.debug("Configured for port: %s, baud: %d", self.port, self.baud)
        self._attr_name = "Tonewinner AT-500"
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Tonewinner",
            model="AT-500",
        )
        self._transport = None
        self._protocol = None
        self._attr_available = False
        self._source_check_task = None

        # Command timeout tracking
        self._last_command_time = None
        self._command_timeout_task = None
        self._pending_command = None
        self._command_timeout_seconds = 30

        # State tracking
        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_sound_mode = None
        self._was_off = True  # Track if device was off to detect power transitions

        # Build source mappings from options
        self._source_code_to_custom_name = {}
        self._custom_name_to_source_code = {}
        source_mappings = entry.options.get(CONF_SOURCE_MAPPINGS, {})
        _LOGGER.debug(
            "Building source mappings from entry.options[%s]: %s",
            CONF_SOURCE_MAPPINGS,
            source_mappings,
        )
        _LOGGER.debug("Available INPUT_SOURCES: %s", INPUT_SOURCES)
        self._attr_source_list = []
        for source_name, source_code in INPUT_SOURCES.items():
            mapping = source_mappings.get(source_code, {})
            _LOGGER.debug(
                "Processing source: %s (code: %s), mapping: %s",
                source_name,
                source_code,
                mapping,
            )
            if not mapping.get("enabled", True):
                _LOGGER.debug("Source disabled: %s (%s)", source_name, source_code)
                continue
            custom_name = mapping.get("name", source_name)
            self._source_code_to_custom_name[source_code] = custom_name
            self._custom_name_to_source_code[custom_name] = source_code
            self._attr_source_list.append(custom_name)
            _LOGGER.debug(
                "Source mapped: %s -> %s (%s)", source_name, custom_name, source_code
            )
        _LOGGER.debug(
            "Final source list: %s",
            self._attr_source_list,
        )
        _LOGGER.debug(
            "Final _custom_name_to_source_code mapping: %s",
            self._custom_name_to_source_code,
        )
        self._attr_sound_mode_list = list(SOUND_MODES.keys())

    async def async_added_to_hass(self) -> None:
        """Connect when entity is added."""
        await self.connect()
        # Query initial state with timeout
        await self._query_all_state_with_timeout()

    async def _query_all_state_with_timeout(self) -> None:
        """Query device for current state with timeout handling."""
        _LOGGER.debug("Querying initial state from device")
        self._start_command_timeout("POWER_QUERY")
        await self.send_raw_command(TonewinnerCommands.POWER_QUERY)
        await asyncio.sleep(0.3)  # Wait for power state response
        await self.send_raw_command(TonewinnerCommands.VOLUME_QUERY)
        await asyncio.sleep(0.3)  # Wait for response
        await self.send_raw_command(TonewinnerCommands.MUTE_QUERY)
        await asyncio.sleep(0.3)  # Wait for response
        await self.send_raw_command(TonewinnerCommands.INPUT_QUERY)
        await asyncio.sleep(0.3)  # Wait for response
        await self.send_raw_command(TonewinnerCommands.MODE_QUERY)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        _LOGGER.debug("Cleaning up before removal")
        # Cancel source check task
        if self._source_check_task:
            self._source_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._source_check_task

        # Cancel command timeout task
        if self._command_timeout_task:
            self._command_timeout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._command_timeout_task

        # Close serial connection
        await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from serial port."""
        _LOGGER.debug("Disconnecting from serial port")
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None
            _LOGGER.info("Serial connection closed")

    async def _query_input_source(self) -> None:
        """Query device for current input source."""
        if self._attr_state != MediaPlayerState.ON:
            _LOGGER.debug("Device is not ON, skipping input source query")
            return
        _LOGGER.info("Querying input source from device")
        self._start_command_timeout("INPUT_QUERY")
        await self.send_raw_command(TonewinnerCommands.INPUT_QUERY)
        # Wait a bit for response to be processed
        await asyncio.sleep(0.2)

    async def connect(self):
        """Establish serial connection."""
        _LOGGER.debug("Attempting connection to %s at %d baud", self.port, self.baud)
        _LOGGER.debug(
            "Serial config: bytesize=%d, parity=%s, stopbits=%d, timeout=%d",
            SERIAL_CONFIG["bytesize"],
            SERIAL_CONFIG["parity"],
            SERIAL_CONFIG["stopbits"],
            SERIAL_CONFIG["timeout"],
        )
        try:
            loop = asyncio.get_event_loop()
            connection = serial_asyncio_fast.create_serial_connection(
                loop,
                lambda: TonewinnerSerialProtocol(self),
                self.port,
                baudrate=self.baud,
                bytesize=SERIAL_CONFIG["bytesize"],
                parity=SERIAL_CONFIG["parity"],
                stopbits=SERIAL_CONFIG["stopbits"],
                timeout=SERIAL_CONFIG["timeout"],
            )
            self._transport, self._protocol = await asyncio.wait_for(
                connection, timeout=5
            )
            _LOGGER.info("Successfully connected to %s", self.port)
        except (TimeoutError, OSError, serial.SerialException) as ex:
            _LOGGER.error("Connection failed: %s", ex)
            self._attr_available = False

    def set_available(self, available: bool):
        """Update availability."""
        _LOGGER.debug("Availability changed: %s", available)
        self._attr_available = available
        self.schedule_update_ha_state()

    def handle_response(self, response: str):
        """Parse incoming data."""
        _LOGGER.debug("RX: %s", response)

        # Response received, clear any pending timeout
        self._cancel_command_timeout()

        # Parse power status
        if (power := TonewinnerProtocol.parse_power_status(response)) is not None:
            new_state = MediaPlayerState.ON if power else MediaPlayerState.OFF
            _LOGGER.debug("State updated: %s", new_state)

            # When power transitions from OFF to ON, query input source
            if new_state == MediaPlayerState.ON and self._was_off:
                _LOGGER.debug("Power turned on (was OFF), querying input source")
                self._was_off = False
                task = asyncio.create_task(self._query_input_source())
                _ = task  # Avoid linting error about unused task
            elif new_state == MediaPlayerState.OFF:
                _LOGGER.debug("Power turned off, clearing source")
                self._attr_source = None
                self._was_off = True

            self._attr_state = new_state

        # Parse volume (device returns 0-80, convert to 0.0-0.8 for HA)
        if (volume := TonewinnerProtocol.parse_volume_status(response)) is not None:
            ha_volume = volume / 100.0
            _LOGGER.debug("Volume updated: device=%.2f, ha=%.2f", volume, ha_volume)
            self._attr_volume_level = ha_volume

        # Parse mute status
        if (mute := TonewinnerProtocol.parse_mute_status(response)) is not None:
            _LOGGER.debug("Mute updated: %s", mute)
            self._attr_is_volume_muted = mute

        # Parse input source
        if (source := TonewinnerProtocol.parse_input_source(response)) is not None:
            source_name, audio_source = source
            _LOGGER.debug("Source code received from device: '%s'", source_name)
            _LOGGER.debug(
                "Available source code mappings: %s", self._source_code_to_custom_name
            )
            _LOGGER.debug(
                "Available custom name mappings: %s", self._custom_name_to_source_code
            )

            # On startup, "eARC/ARC" is sent rather than eARC/ARC source name
            if source_name == "eARC/ARC":
                self._attr_source = "ARC"

            # Map source code to custom name
            source_code = self._custom_name_to_source_code.get(source_name)
            if source_code:
                _LOGGER.info("Source updated: '%s' -> '%s'", source_code, source_name)
                self._attr_source = source_name
            elif audio_source:
                custom_name_from_audio_source = self._source_code_to_custom_name.get(
                    audio_source
                )
                _LOGGER.info(
                    "Source updated from audio source: '%s' -> '%s'",
                    audio_source,
                    custom_name_from_audio_source,
                )
                self._attr_source = custom_name_from_audio_source
            else:
                _LOGGER.warning(
                    "Unknown source code received: '%s', mapping it directly",
                    source_name,
                )
                _LOGGER.warning(
                    "Available source codes: %s",
                    list(self._source_code_to_custom_name.keys()),
                )
                self._attr_source = source_name

        # Parse sound mode
        if (mode := TonewinnerProtocol.parse_sound_mode(response)) is not None:
            _LOGGER.debug("Sound mode updated: %s", mode)
            self._attr_sound_mode = mode

        _LOGGER.debug(
            "Writing HA state with: state=%s, volume=%.2f, mute=%s, source=%s, mode=%s",
            self._attr_state,
            self._attr_volume_level,
            self._attr_is_volume_muted,
            self._attr_source,
            self._attr_sound_mode,
        )
        self.async_write_ha_state()

        # Periodically check for source if device is ON but source is unknown
        if self._attr_state == MediaPlayerState.ON and not self._attr_source:
            if self._source_check_task is None or self._source_check_task.done():
                _LOGGER.debug("Device ON but source unknown, scheduling periodic check")
                self._source_check_task = asyncio.create_task(
                    self._periodic_source_check()
                )

    async def _periodic_source_check(self) -> None:
        """Periodically check for input source when device is ON but source is unknown."""
        max_attempts = 5
        attempt = 0
        while self._attr_state == MediaPlayerState.ON and attempt < max_attempts:
            if self._attr_source:
                _LOGGER.debug("Source now known, stopping periodic check")
                break
            attempt += 1
            _LOGGER.debug(
                "Periodic source check (attempt %d/%d)", attempt, max_attempts
            )
            await self._query_input_source()
            # Wait 3 seconds before next check
            await asyncio.sleep(3)
        _LOGGER.debug("Periodic source check completed after %d attempts", attempt)

    async def send_raw_command(self, command: str):
        """Service handler: send raw command."""
        _LOGGER.debug("Preparing to send command: %s", command)
        if not self._transport:
            raise TonewinnerError("Not connected")

        # If command is not a query, start timeout tracking
        if not command.endswith("?"):
            self._start_command_timeout(f"CMD:{command[:10]}")

        # Handle hex strings like "0x21 0x50" or plain ASCII
        if command.startswith("0x"):
            data = bytes([int(x, 16) for x in command.split()])
        else:
            # Wrap in protocol markers if not already present
            if not command.startswith("##"):
                command = TonewinnerProtocol.build_command(command)
            data = command.encode("ascii")

        _LOGGER.debug("TX bytes: %s", data.hex())
        self._transport.write(data)
        _LOGGER.debug("Command sent successfully")
        _LOGGER.debug("Pending commands: %s", self._pending_command)

    # --- Media player controls ---

    async def async_turn_on(self):
        """Turn the media player on."""
        _LOGGER.debug("Turning on receiver")
        self._start_command_timeout("POWER_ON")
        await self.send_raw_command(TonewinnerCommands.POWER_ON)
        # Set optimistic state - command sent successfully, receiver should be turning on
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()
        # Note: The device will respond to POWER_ON with the actual power state,
        # which will trigger the input source query in handle_response
        # when it receives "POWER ON"

    async def async_turn_off(self):
        """Turn the media player off."""
        _LOGGER.debug("Turning off receiver")
        await self.send_raw_command(TonewinnerCommands.POWER_OFF)
        # Set optimistic state - command sent successfully, receiver should be turning off
        self._attr_state = MediaPlayerState.OFF
        # Clear source state when turning off
        self._attr_source = None
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (HA 0.0-1.0, device 0-80). Uses only part of the input range."""
        vol_device = min(volume * 100.0, 80)
        command = f"VOL {vol_device}"
        _LOGGER.debug("Setting volume: HA=%.2f, device=%d", volume, vol_device)
        await self.send_raw_command(command)
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Volume up media player."""
        _LOGGER.debug("Volume up")
        await self.send_raw_command(TonewinnerCommands.VOLUME_UP)

    async def async_volume_down(self):
        """Volume down media player."""
        _LOGGER.debug("Volume down")
        await self.send_raw_command(TonewinnerCommands.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media player."""
        command = TonewinnerCommands.MUTE_ON if mute else TonewinnerCommands.MUTE_OFF
        _LOGGER.debug("Setting mute: %s", mute)
        await self.send_raw_command(command)
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        _LOGGER.debug("async_select_source called with: %s", source)
        _LOGGER.debug(
            "Available sources in _custom_name_to_source_code: %s",
            self._custom_name_to_source_code,
        )
        _LOGGER.debug(
            "Available sources in source_list: %s",
            self._attr_source_list,
        )
        if (
            source not in self._custom_name_to_source_code
            and source not in self._source_code_to_custom_name
        ):
            _LOGGER.warning(
                "Unknown source '%s'. Available sources: %s",
                source,
                list(self._custom_name_to_source_code.keys()),
            )
            raise ValueError(f"Unknown source: {source}")
        source_code = self._custom_name_to_source_code.get(source, source)
        command = f"SI {source_code}"
        _LOGGER.debug(
            "Selecting source: %s -> %s (command: %s)", source, source_code, command
        )
        await self.send_raw_command(command)
        self.async_write_ha_state()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode not in SOUND_MODES:
            raise ValueError(f"Unknown sound mode: {sound_mode}")
        command = f"{TonewinnerCommands.MODE_PREFIX} {SOUND_MODES[sound_mode]}"
        _LOGGER.debug("Selecting sound mode: %s (command: %s)", sound_mode, command)
        await self.send_raw_command(command)
        self.async_write_ha_state()

    def _start_command_timeout(self, command: str) -> None:
        """Start timeout tracking for a command."""
        _LOGGER.debug("Starting timeout for command: %s", command)
        self._pending_command = command
        self._last_command_time = asyncio.get_event_loop().time()

        # Cancel existing timeout task
        if self._command_timeout_task:
            self._command_timeout_task.cancel()

        # Create new timeout task
        self._command_timeout_task = asyncio.create_task(
            self._command_timeout_handler(command)
        )

    def _cancel_command_timeout(self) -> None:
        """Cancel pending command timeout."""
        if self._command_timeout_task:
            _LOGGER.debug("Cancelling command timeout")
            self._command_timeout_task.cancel()
            self._command_timeout_task = None
        self._pending_command = None

    async def _command_timeout_handler(self, command: str) -> None:
        """Handle command timeout by marking device unavailable."""
        await asyncio.sleep(self._command_timeout_seconds)

        # Check if still pending (response may have arrived)
        if self._pending_command == command:
            if self._attr_state == MediaPlayerState.OFF:
                _LOGGER.info("Device is off, ignoring timeout")
            else:
                _LOGGER.warning(
                    "Command '%s' timed out after %d seconds, marking unavailable",
                    command,
                    self._command_timeout_seconds,
                )
                self._attr_available = False
                self.async_write_ha_state()
            self._command_timeout_task = None
            self._pending_command = None
