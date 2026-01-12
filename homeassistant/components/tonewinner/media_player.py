"""Tonewinner AT-500 media player."""

import asyncio
import logging

import serial
import serial_asyncio_fast
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.core import ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(hass, config_entry, async_add_entities):
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

    _available = False

    def __init__(self, hass, entry, data):
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
        self._available = False

    async def async_added_to_hass(self):
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
        except Exception as ex:
            _LOGGER.error("Connection failed: %s", ex)
            self._available = False

    def set_available(self, available: bool):
        """Update availability."""
        self._available = available
        self.schedule_update_ha_state()

    def handle_response(self, response: str):
        """Parse incoming data."""
        _LOGGER.debug(f"RX: {response}")
        # TODO: Update self._attr_state, volume, source based on response

    async def send_raw_command(self, command: str):
        """Service handler: send raw command."""
        if not self._transport:
            raise Exception("Not connected")

        # Handle hex strings like "0x21 0x50" or plain ASCII
        if command.startswith("0x"):
            data = bytes(int(x, 16) for x in command.split())
        else:
            data = command.encode("ascii")

        self._transport.write(data)
        if not data.endswith(b"\r") and not data.endswith(b"\n"):
            self._transport.write(b"\r")  # Common terminator

    # --- Media player controls (Integra-style stubs) ---

    @property
    def available(self):
        return self._available

    async def async_turn_on(self):
        await self.send_raw_command("PWR01")

    async def async_turn_off(self):
        await self.send_raw_command("PWR00")

    async def async_set_volume_level(self, volume):
        vol_int = int(volume * 100)
        await self.send_raw_command(f"VL{vol_int:03d}")
