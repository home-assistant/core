"""Tonewinner AT-500 media player."""

import asyncio
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

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN
from .protocol import ToneWinnerCommands, ToneWinnerProtocol

_LOGGER = logging.getLogger(__name__)


class TonewinnerError(Exception):
    """Exception for Tonewinner errors."""


# Map source names to command suffixes
INPUT_SOURCES = {
    "HDMI 1": "HD1",
    "HDMI 2": "HD2",
    "HDMI 3": "HD3",
    "HDMI 4": "HD4",
    "Optical 1": "OP1",
    "Optical 2": "OP2",
    "Coaxial 1": "CO1",
    "Coaxial 2": "CO2",
    "Analog": "AN1",
    "Bluetooth": "BT",
    "USB": "USB",
    "PC": "PC",
    "ARC": "ARC",
}

# Map sound mode names to command codes
SOUND_MODES = {
    mode.label: command for command, mode in ToneWinnerCommands.MODES.items()
}


# Service registration schema
SERVICE_SEND_RAW = "send_raw"
SERVICE_SEND_RAW_SCHEMA = vol.Schema(
    {
        vol.Required("command"): cv.string,
    }
)

SERIAL_CONFIG = {
    "baudrate": 9600,
    "bytesize": serial.SEVENBITS,  # istrip: 7-bit data
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

    # Create the entity
    data = hass.data[DOMAIN][config_entry.entry_id]
    entity = TonewinnerMediaPlayer(hass, config_entry, data)
    async_add_entities([entity])

    # Register the service HERE – hass is available in this function
    async def handle_send_raw(call: ServiceCall):
        command = call.data["command"]
        await entity.send_raw_command(command)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_RAW, handle_send_raw, schema=SERVICE_SEND_RAW_SCHEMA
    )

    # Store handle for cleanup
    hass.data[DOMAIN][f"{config_entry.entry_id}_service"] = handle_send_raw


class TonewinnerProtocol(asyncio.Protocol):
    """Tonewinner AT-500 protocol implementation."""

    def __init__(self, entity):
        """Initialize TonewinnerProtocol."""
        self.entity = entity
        self.transport = None
        self.buffer = b""

    def connection_made(self, transport):
        """Connection made."""
        self.transport = transport
        self.entity.set_available(True)

    def data_received(self, data):
        """Data received."""
        self.buffer += data

        # Parse ToneWinner protocol: messages start with '#' and end with '*'
        # with no newlines. Messages may arrive in multiple chunks.
        while True:
            # Find start of next message
            start_idx = self.buffer.find(b"#")
            if start_idx == -1:
                # No start marker in buffer, clear it
                self.buffer = b""
                break

            # Find end of message
            end_idx = self.buffer.find(b"*", start_idx)
            if end_idx == -1:
                # Incomplete message (no end marker), keep data from '#'
                self.buffer = self.buffer[start_idx:]
                break

            # Extract message content (between # and *)
            message = self.buffer[start_idx + 1 : end_idx]
            if message:
                self.entity.handle_response(message.decode("ascii", errors="ignore"))

            # Remove processed message from buffer
            self.buffer = self.buffer[end_idx + 1 :]

    def connection_lost(self, exc):
        """Connection lost."""
        self.entity.set_available(False)


class TonewinnerMediaPlayer(MediaPlayerEntity):
    """Tonewinner AT-500 media player."""

    _transport: None | serial_asyncio_fast.SerialTransport
    _protocol: None | asyncio.Protocol

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
        self.hass = hass
        self.port = data[CONF_SERIAL_PORT]
        self.baud = data.get(CONF_BAUD_RATE, 9600)
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

        # State tracking
        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_sound_mode = None
        self._attr_source_list = list(INPUT_SOURCES.keys())
        self._attr_sound_mode_list = list(SOUND_MODES.keys())

    async def async_added_to_hass(self) -> None:
        """Connect when entity is added."""
        await self.connect()

    async def connect(self):
        """Establish serial connection."""
        try:
            loop = asyncio.get_event_loop()
            connection = serial_asyncio_fast.create_serial_connection(
                loop,
                lambda: TonewinnerProtocol(self),
                self.port,
                baudrate=self.baud,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            self._transport, self._protocol = await asyncio.wait_for(
                connection, timeout=5
            )
        except (TimeoutError, OSError, serial.SerialException) as ex:
            _LOGGER.error("Connection failed: %s", ex)
            self._attr_available = False

    def set_available(self, available: bool):
        """Update availability."""
        self._attr_available = available
        self.schedule_update_ha_state()

    def handle_response(self, response: str):
        """Parse incoming data."""
        _LOGGER.debug("RX: %s", response)

        # Parse power status
        if power := ToneWinnerProtocol.parse_power_status(response):
            self._attr_state = MediaPlayerState.ON if power else MediaPlayerState.OFF

        # Parse volume (device returns 0-80, convert to 0.0-1.0 for HA)
        if volume := ToneWinnerProtocol.parse_volume_status(response):
            self._attr_volume_level = volume / 80.0

        # Parse mute status
        if mute := ToneWinnerProtocol.parse_mute_status(response):
            self._attr_is_volume_muted = mute

        # Parse input source
        if source := ToneWinnerProtocol.parse_input_source(response):
            self._attr_source = source

        # Parse sound mode
        if mode := ToneWinnerProtocol.parse_sound_mode(response):
            self._attr_sound_mode = mode

        self.async_write_ha_state()

    async def send_raw_command(self, command: str):
        """Service handler: send raw command."""
        if not self._transport:
            raise TonewinnerError("Not connected")

        # Handle hex strings like "0x21 0x50" or plain ASCII
        if command.startswith("0x"):
            data = bytes(int(x, 16) for x in command.split())
        else:
            # Wrap in protocol markers if not already present
            if not command.startswith("##"):
                command = ToneWinnerProtocol.build_command(command)
            data = command.encode("ascii")

        self._transport.write(data)

    # --- Media player controls ---

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.send_raw_command(ToneWinnerCommands.POWER_ON)
        self._attr_state = MediaPlayerState.ON

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.send_raw_command(ToneWinnerCommands.POWER_OFF)
        self._attr_state = MediaPlayerState.OFF

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (HA 0.0-1.0, device 0-80)."""
        vol_device = int(volume * 80.0)
        command = f"VOL {vol_device}"
        await self.send_raw_command(command)
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Volume up media player."""
        await self.send_raw_command(ToneWinnerCommands.VOLUME_UP)

    async def async_volume_down(self):
        """Volume down media player."""
        await self.send_raw_command(ToneWinnerCommands.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media player."""
        command = ToneWinnerCommands.MUTE_ON if mute else ToneWinnerCommands.MUTE_OFF
        await self.send_raw_command(command)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source not in INPUT_SOURCES:
            raise ValueError(f"Unknown source: {source}")
        command = f"SI {INPUT_SOURCES[source]}"
        await self.send_raw_command(command)
        self._attr_source = source
        self.async_write_ha_state()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode not in SOUND_MODES:
            raise ValueError(f"Unknown sound mode: {sound_mode}")
        command = f"{ToneWinnerCommands.MODE_PREFIX} {SOUND_MODES[sound_mode]}"
        await self.send_raw_command(command)
        self._attr_sound_mode = sound_mode
        self.async_write_ha_state()
