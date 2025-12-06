"""Coordinator for ToneWinner AT-500 integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import serial_asyncio_fast as serial_asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CMD_MUTE_QUERY,
    CMD_POWER_QUERY,
    CMD_VOLUME_QUERY,
    COMMAND_TERMINATOR,
    CONF_BAUDRATE,
    CONF_SERIAL_PORT,
    DEFAULT_BAUDRATE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = 30  # Poll device every 30 seconds


class ToneWinnerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage the serial connection and device state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.port = entry[CONF_SERIAL_PORT]
        self.baudrate = entry.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()
        self._response_event: asyncio.Event = asyncio.Event()
        self._last_response: str = ""
        self._command_task: asyncio.Task | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
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
        except Exception as err:
            _LOGGER.error("Failed to connect to %s: %s", self.port, err)
            raise

    async def _disconnect(self) -> None:
        """Close serial connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def _process_commands(self) -> None:
        """Background task to process commands from the queue."""
        while True:
            try:
                command = await self._command_queue.get()
                if not self._writer or not self._reader:
                    await self._connect()

                _LOGGER.debug("Sending command: %s", command.strip())
                self._writer.write(command.encode())
                await self._writer.drain()

                # Read response
                response = await self._reader.readuntil(COMMAND_TERMINATOR.encode())
                self._last_response = response.decode().strip()
                _LOGGER.debug("Received response: %s", self._last_response)
                self._response_event.set()

            except TimeoutError:
                _LOGGER.warning("Timeout waiting for response to %s", command)
            except Exception as err:
                _LOGGER.error("Error processing command %s: %s", command, err)
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
            return self._last_response
        except TimeoutError:
            _LOGGER.error("Timeout waiting for command response")
            return ""

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device status by polling."""
        try:
            # Query device status
            power_response = await self.send_command(CMD_POWER_QUERY)
            volume_response = await self.send_command(CMD_VOLUME_QUERY)
            mute_response = await self.send_command(CMD_MUTE_QUERY)

            data: dict[str, Any] = {
                "power": self._parse_power(power_response),
                "volume": self._parse_volume(volume_response),
                "mute": self._parse_mute(mute_response),
            }

            _LOGGER.debug("Device status: %s", data)
            return data

        except Exception as err:
            _LOGGER.error("Error updating device data: %s", err)
            await self._disconnect()
            raise UpdateFailed(f"Failed to update device data: {err}")

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

    async def async_power_on(self) -> None:
        """Turn device on."""
        await self.send_command("PWR01")

    async def async_power_off(self) -> None:
        """Turn device off."""
        await self.send_command("PWR00")

    async def async_set_volume(self, volume: float) -> None:
        """Set volume (0-100)."""
        # Convert 0-100 to 0-128 hex
        vol_value = int((volume / 100) * 128)
        vol_hex = f"{vol_value:02X}"
        await self.send_command(f"MVL{vol_hex}")

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self.send_command(CMD_VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self.send_command(CMD_VOLUME_DOWN)

    async def async_mute(self, mute: bool) -> None:
        """Set mute state."""
        await self.send_command("AMT01" if mute else "AMT00")

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        await self._connect()
        self._command_task = asyncio.create_task(self._process_commands())
        _LOGGER.debug("Coordinator setup complete")

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                pass

        await self._disconnect()
        _LOGGER.debug("Coordinator shutdown complete")
