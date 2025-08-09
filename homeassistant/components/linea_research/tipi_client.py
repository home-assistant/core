"""TIPI Protocol client for Linea Research amplifiers."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 10001
CONNECTION_TIMEOUT = 10
RESPONSE_TIMEOUT = 5


class TIPIProtocolError(Exception):
    """Base exception for TIPI protocol errors."""


class TIPIConnectionError(TIPIProtocolError):
    """Exception for connection errors."""


class TIPIClient:
    """Client for TIPI protocol communication with Linea Research amplifiers."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize the TIPI client."""
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._connected = False

    async def connect(self) -> None:
        """Connect to the amplifier."""
        if self._connected:
            return

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECTION_TIMEOUT,
            )
            self._connected = True
            _LOGGER.debug("Connected to Linea Research amplifier at %s:%s", self.host, self.port)
        except (asyncio.TimeoutError, OSError) as err:
            raise TIPIConnectionError(f"Failed to connect to {self.host}:{self.port}") from err

    async def disconnect(self) -> None:
        """Disconnect from the amplifier."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
            self._connected = False
            _LOGGER.debug("Disconnected from Linea Research amplifier")

    async def _send_command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a TIPI command and return the response."""
        if not self._connected:
            await self.connect()

        async with self._lock:
            command = {
                "jsonrpc": "2.0",
                "method": method,
                "id": 1,
            }
            if params:
                command["params"] = params

            # Send command
            json_command = json.dumps(command) + "\n"
            _LOGGER.debug("Sending TIPI command: %s", json_command.strip())
            
            try:
                self._writer.write(json_command.encode())
                await self._writer.drain()

                # Read response
                response_data = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=RESPONSE_TIMEOUT,
                )
                
                response_str = response_data.decode().strip()
                _LOGGER.debug("Received TIPI response: %s", response_str)
                
                response = json.loads(response_str)
                
                if "error" in response:
                    raise TIPIProtocolError(f"TIPI error: {response['error']}")
                
                return response.get("result", {})
                
            except (asyncio.TimeoutError, ConnectionError, OSError) as err:
                self._connected = False
                raise TIPIConnectionError(f"Communication error: {err}") from err
            except json.JSONDecodeError as err:
                raise TIPIProtocolError(f"Invalid JSON response: {err}") from err

    async def get_power_state(self) -> bool:
        """Get the power state of the amplifier."""
        # Using System::GetStandby to check if in standby (sleep) mode
        result = await self._send_command("System::GetStandby")
        # Returns true if in standby, so power is on when NOT in standby
        return not result.get("value", True)

    async def set_power_on(self) -> None:
        """Turn the amplifier on (exit standby)."""
        # Set standby to false to turn on
        await self._send_command("System::SetStandby", {"value": False})

    async def set_power_off(self) -> None:
        """Turn the amplifier off (enter standby)."""
        # Set standby to true to turn off
        await self._send_command("System::SetStandby", {"value": True})

    async def get_sleep_state(self) -> bool:
        """Get the sleep state of the amplifier."""
        # Using System::GetStandby to check sleep state
        result = await self._send_command("System::GetStandby")
        return result.get("value", False)

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        info = {}
        
        try:
            # Get various device info using available TIPI methods
            frame_info = await self._send_command("System::GetFrameInfo")
            info["model"] = frame_info.get("value", {}).get("model", "Unknown")
            info["serial"] = frame_info.get("value", {}).get("serial", "Unknown")
            
            # Get firmware version
            firmware = await self._send_command("System::GetFirmwareInfo")
            info["firmware"] = firmware.get("value", {}).get("version", "Unknown")
            
        except TIPIProtocolError:
            _LOGGER.warning("Failed to get complete device info")
            
        return info

    async def get_status(self) -> dict[str, Any]:
        """Get current status of the amplifier."""
        status = {}
        
        try:
            # Get power/standby state
            standby_result = await self._send_command("System::GetStandby")
            status["standby"] = standby_result.get("value", True)
            status["power"] = not status["standby"]
            
            # Get mute states for channels
            try:
                mute_a = await self._send_command("Amplifier::GetMuteA")
                status["mute_a"] = mute_a.get("value", False)
            except TIPIProtocolError:
                pass
                
            try:
                mute_b = await self._send_command("Amplifier::GetMuteB")
                status["mute_b"] = mute_b.get("value", False)
            except TIPIProtocolError:
                pass
                
            # Get gain settings
            try:
                gain_a = await self._send_command("Amplifier::GetGainA")
                status["gain_a"] = gain_a.get("value", 0)
            except TIPIProtocolError:
                pass
                
            try:
                gain_b = await self._send_command("Amplifier::GetGainB")
                status["gain_b"] = gain_b.get("value", 0)
            except TIPIProtocolError:
                pass
                
        except TIPIProtocolError as err:
            _LOGGER.error("Failed to get amplifier status: %s", err)
            
        return status