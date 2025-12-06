"""Coordinator for ToneWinner AT-500 integration."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging
from typing import Any

# serial_asyncio_fast is the correct import for Home Assistant
import serial_asyncio_fast as serial_asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CMD_MUTE_OFF,
    CMD_MUTE_ON,
    CMD_MUTE_QUERY,
    CMD_POWER_OFF,
    CMD_POWER_ON,
    CMD_POWER_QUERY,
    CMD_VOLUME_DOWN,
    CMD_VOLUME_QUERY,
    CMD_VOLUME_SET,
    CMD_VOLUME_UP,
    COMMAND_TERMINATOR,
    CONF_BAUDRATE,
    DEFAULT_BAUDRATE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


type ToneWinnerConfigEntry = ConfigEntry[ToneWinnerCoordinator]


class ToneWinnerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage the serial connection and device state."""

    config_entry: ToneWinnerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ToneWinnerConfigEntry) -> None:
        """Initialize the coordinator."""
        self.port = entry.data[CONF_DEVICE]
        self.baudrate = entry.data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()
        self._response_event: asyncio.Event = asyncio.Event()
        self._last_response: str = ""
        self._command_task: asyncio.Task | None = None
        self._shutdown = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _connect(self) -> None:
        """Establish serial connection."""
        try:
            _LOGGER.debug("Connecting to %s at %d baud", self.port, self.baudrate)
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate,
                timeout=DEFAULT_TIMEOUT,
            )
            _LOGGER.info("Successfully connected to %s", self.port)
        except OSError as err:
            _LOGGER.error("Failed to connect to %s: %s", self.port, err)
            raise UpdateFailed(f"Serial connection failed: {err}") from err

    async def _disconnect(self) -> None:
        """Close serial connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as err:  # noqa: BLE001 - catching all exceptions for cleanup
                _LOGGER.debug("Error closing serial connection: %s", err)
        self._reader = None
        self._writer = None

    async def _process_commands(self) -> None:
        """Background task to process commands from the queue."""
        while not self._shutdown:
            try:
                command = await self._command_queue.get()
                if self._writer is None or self._reader is None:
                    await self._connect()

                _LOGGER.debug("Sending command: %s", command.strip())
                assert self._writer is not None
                self._writer.write(command.encode())
                await self._writer.drain()

                # Read response
                assert self._reader is not None
                response = await self._reader.readuntil(COMMAND_TERMINATOR.encode())
                self._last_response = response.decode().strip()
                _LOGGER.debug("Received response: %s", self._last_response)
                self._response_event.set()

            except TimeoutError:
                _LOGGER.warning("Timeout waiting for response")
            except OSError as err:
                _LOGGER.error("Serial error processing command: %s", err)
                await self._disconnect()
            finally:
                self._command_queue.task_done()

    async def send_command(self, command: str) -> str:
        """Send a command and return the response."""
        if not command.endswith(COMMAND_TERMINATOR):
            command += COMMAND_TERMINATOR

        await self._command_queue.put(command)
        self._response_event.clear()

        try:
            await asyncio.wait_for(
                self._response_event.wait(),
                timeout=DEFAULT_TIMEOUT * 2,
            )
        except TimeoutError:
            _LOGGER.error("Timeout waiting for command response")
            return ""
        else:
            return self._last_response

    def _parse_power(self, response: str) -> bool | None:
        """Parse power status from response."""
        if response.startswith("PWR"):
            try:
                return response[3:5] == "01"
            except (ValueError, IndexError):
                pass
        return None

    def _parse_volume(self, response: str) -> float | None:
        """Parse volume level from response (0-100)."""
        if response.startswith("MVL"):
            try:
                # Convert from hex (00-80 = 0-128, scales to 0-100)
                vol_hex = response[3:5]
                vol_value = int(vol_hex, 16)
                return min(100.0, (vol_value / 128) * 100)
            except (ValueError, IndexError):
                pass
        return None

    def _parse_mute(self, response: str) -> bool | None:
        """Parse mute status from response."""
        if response.startswith("AMT"):
            try:
                return response[3:5] == "01"
            except (ValueError, IndexError):
                pass
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device status by polling."""
        # Query device status
        power_response = await self.send_command(CMD_POWER_QUERY + COMMAND_TERMINATOR)
        volume_response = await self.send_command(CMD_VOLUME_QUERY + COMMAND_TERMINATOR)
        mute_response = await self.send_command(CMD_MUTE_QUERY + COMMAND_TERMINATOR)

        data: dict[str, Any] = {
            "power": self._parse_power(power_response),
            "volume": self._parse_volume(volume_response),
            "mute": self._parse_mute(mute_response),
        }

        _LOGGER.debug("Device status: %s", data)
        return data

    async def async_power_on(self) -> None:
        """Turn device on."""
        await self.send_command(CMD_POWER_ON + COMMAND_TERMINATOR)

    async def async_power_off(self) -> None:
        """Turn device off."""
        await self.send_command(CMD_POWER_OFF + COMMAND_TERMINATOR)

    async def async_set_volume(self, volume: float) -> None:
        """Set volume (0-100)."""
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")

        # Convert 0-100 to 0-128 hex
        vol_value = int((volume / 100) * 128)
        vol_hex = f"{vol_value:02X}"
        await self.send_command(f"{CMD_VOLUME_SET}{vol_hex}{COMMAND_TERMINATOR}")

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self.send_command(CMD_VOLUME_UP + COMMAND_TERMINATOR)

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self.send_command(CMD_VOLUME_DOWN + COMMAND_TERMINATOR)

    async def async_mute(self, mute: bool) -> None:
        """Set mute state."""
        command = CMD_MUTE_ON if mute else CMD_MUTE_OFF
        await self.send_command(command + COMMAND_TERMINATOR)

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        await self._connect()
        self._command_task = asyncio.create_task(self._process_commands())
        _LOGGER.debug("Coordinator setup complete")

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        self._shutdown = True

        # Cancel command task
        if self._command_task:
            self._command_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._command_task

        await self._disconnect()
        _LOGGER.debug("Coordinator shutdown complete")
