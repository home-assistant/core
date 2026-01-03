"""Tonewinner AT-500 media player."""

import asyncio

import serial_asyncio
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.core import ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN

# Service registration schema
SERVICE_SEND_RAW = "send_raw"
SERVICE_SEND_RAW_SCHEMA = vol.Schema(
    {
        vol.Required("command"): cv.string,
    }
)


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
        # Simple line-based parsing (adjust terminator as needed)
        if b"\r" in self.buffer:
            lines = self.buffer.split(b"\r")
            self.buffer = lines[-1]
            for line in lines[:-1]:
                if line:
                    self.entity.handle_response(line.decode("ascii", errors="ignore"))

    def connection_lost(self, exc):
        """Connection lost."""
        self.entity.set_available(False)


class TonewinnerMediaPlayer(MediaPlayerEntity):
    """Tonewinner AT-500 media player."""

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
            coro = serial_asyncio.create_serial_connection(
                loop,
                lambda: TonewinnerProtocol(self),
                self.port,
                self.baud,
                timeout=1,
            )
            self._transport, self._protocol = await asyncio.wait_for(coro, timeout=5)
        except Exception as ex:
            self.hass.logger.error(f"Connection failed: {ex}")
            self._available = False

    def set_available(self, available: bool):
        """Update availability."""
        self._available = available
        self.schedule_update_ha_state()

    def handle_response(self, response: str):
        """Parse incoming data."""
        self.hass.logger.debug(f"RX: {response}")
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
