"""API for communicating with Briiv air purifiers over UDP with comprehensive traffic logging."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from datetime import datetime
import json
import logging
import socket
from typing import Any, ClassVar

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

LOGGER = logging.getLogger(f"homeassistant.components.{DOMAIN}.api")


class BriivError(HomeAssistantError):
    """Briiv base error."""


class BriivCallbackError(BriivError):
    """Briiv callback error."""


class BriivTrafficLogger:
    """Logger for UDP traffic."""

    def __init__(self) -> None:
        """Initialize the traffic logger."""
        self.logger = logging.getLogger(f"homeassistant.components.{DOMAIN}.traffic")

    def log_outgoing(
        self, data: bytes, dest_addr: tuple[str, int] | str, serial: str
    ) -> None:
        """Log outgoing UDP traffic."""
        timestamp = datetime.now().isoformat()
        try:
            decoded_data = data.decode()
            self.logger.debug(
                "[%s] 🔼 OUT -> %s (Serial: %s) | %s",
                timestamp,
                dest_addr,
                serial,
                decoded_data,
            )
        except UnicodeDecodeError as err:
            self.logger.debug(
                "[%s] 🔼 OUT -> %s (Serial: %s) | Failed decode: %s | Raw: %s",
                timestamp,
                dest_addr,
                serial,
                err,
                data.hex(),
            )

    def log_incoming(
        self,
        data: bytes,
        addr: tuple[str, int],
        parsed_data: dict[str, Any] | None = None,
    ) -> None:
        """Log incoming UDP traffic."""
        timestamp = datetime.now().isoformat()
        try:
            decoded_data = data.decode()
            if parsed_data:
                self.logger.debug(
                    "[%s] 🔽 IN <- %s:%d | Raw: %s | Parsed: %s",
                    timestamp,
                    addr[0],
                    addr[1],
                    decoded_data,
                    parsed_data,
                )
            else:
                self.logger.debug(
                    "[%s] 🔽 IN <- %s:%d | Raw: %s",
                    timestamp,
                    addr[0],
                    addr[1],
                    decoded_data,
                )
        except UnicodeDecodeError as err:
            self.logger.debug(
                "[%s] 🔽 IN <- %s:%d | Failed decode: %s | Raw: %s",
                timestamp,
                addr[0],
                addr[1],
                err,
                data.hex(),
            )


class BriivCommands:
    """Command definitions for Briiv devices."""

    SPEED_MAPPING = {0: 0, 1: 25, 2: 50, 3: 75, 4: 100}

    @staticmethod
    def create_command(
        serial_number: str,
        command_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a command dictionary with the required format."""
        cmd = {"serial_number": serial_number, "command": command_type, **kwargs}
        LOGGER.debug("Created command: %s", cmd)
        return cmd

    @staticmethod
    def power_command(
        serial_number: str,
        state: bool,
    ) -> dict[str, Any]:
        """Create power on/off command."""
        LOGGER.debug(
            "Creating power command: serial=%s, state=%s", serial_number, state
        )
        return BriivCommands.create_command(
            serial_number=serial_number, command_type="power", power=1 if state else 0
        )

    @staticmethod
    def fan_speed_command(
        serial_number: str,
        speed: int,
    ) -> dict[str, Any]:
        """Create fan speed command."""
        LOGGER.debug(
            "Creating fan speed command: serial=%s, speed=%s", serial_number, speed
        )
        return BriivCommands.create_command(
            serial_number=serial_number, command_type="fan_speed", fan_speed=speed
        )

    @staticmethod
    def boost_command(
        serial_number: str,
        boost: bool,
    ) -> dict[str, Any]:
        """Create boost mode command."""
        LOGGER.debug(
            "Creating boost command: serial=%s, boost=%s", serial_number, boost
        )
        return BriivCommands.create_command(
            serial_number=serial_number, command_type="boost", boost=1 if boost else 0
        )


class BriivAPI:
    """API class to handle UDP communication with Briiv devices."""

    _instances: ClassVar[dict[str, BriivAPI]] = {}
    _shared_socket: ClassVar[socket.socket | None] = None
    _shared_read_task: ClassVar[asyncio.Task | None] = None
    _is_listening: ClassVar[bool] = False
    _device_addresses: ClassVar[dict[str, tuple[str, int]]] = {}
    _traffic_logger: ClassVar[BriivTrafficLogger] = BriivTrafficLogger()
    _discovered_devices: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(
        self, host: str = "0.0.0.0", port: int = 3334, serial_number: str | None = None
    ) -> None:
        """Initialize the API."""
        self.host = host
        self.port = port
        self.serial_number = serial_number
        self.callbacks: list[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = []

        if serial_number:
            self._instances[serial_number] = self
            LOGGER.debug("Registered device instance for %s", serial_number)

    async def send_command(self, command: dict[str, Any]) -> None:
        """Send a command to the Briiv device."""
        if not self._shared_socket:
            raise BriivError("Shared socket not initialized")

        try:
            data = json.dumps(command).encode()
            serial = command.get("serial_number")

            if not serial:
                raise BriivError("Command missing serial number")

            # Get device address if known
            dest_addr = self._device_addresses.get(serial)

            if dest_addr:
                # Send to specific device
                self._traffic_logger.log_outgoing(data, dest_addr, serial)
                await asyncio.get_running_loop().sock_sendto(
                    self._shared_socket, data, dest_addr
                )
            else:
                # Fall back to broadcast if device address unknown
                broadcast_addr = ("255.255.255.255", self.port)
                self._traffic_logger.log_outgoing(data, broadcast_addr, serial)
                await asyncio.get_running_loop().sock_sendto(
                    self._shared_socket, data, broadcast_addr
                )

        except (OSError, json.JSONDecodeError) as err:
            LOGGER.error("Failed to send command: %s", err)
            raise BriivError(f"Failed to send command: {err}") from err

    async def set_power(self, state: bool) -> None:
        """Set power state."""
        LOGGER.debug("Setting power state to: %s", state)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.power_command(self.serial_number, state)
        await self.send_command(command)
        LOGGER.debug("Power command sent: %s", command)

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed."""
        LOGGER.debug("Setting fan speed to: %s", speed)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.fan_speed_command(self.serial_number, speed)
        await self.send_command(command)
        LOGGER.debug("Fan speed command sent: %s", command)

    async def set_boost(self, boost: bool) -> None:
        """Set boost mode."""
        LOGGER.debug("Setting boost mode to: %s", boost)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.boost_command(self.serial_number, boost)
        await self.send_command(command)
        LOGGER.debug("Boost command sent: %s", command)

    @classmethod
    def _create_and_bind_socket(cls) -> socket.socket:
        """Create and bind the shared socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Try binding to all interfaces first, fall back to localhost
        try:
            sock.bind(("0.0.0.0", 3334))
        except OSError:
            try:
                sock.bind(("127.0.0.1", 3334))
            except OSError as err:
                sock.close()
                raise BriivError(f"Failed to bind socket: {err}") from err

        sock.setblocking(False)
        return sock

    @classmethod
    async def start_shared_listener(cls, loop: asyncio.AbstractEventLoop) -> None:
        """Start a shared UDP listener for all instances."""
        if cls._is_listening:
            return

        try:
            cls._shared_socket = cls._create_and_bind_socket()
            LOGGER.debug("Socket created and bound successfully")

            cls._shared_read_task = asyncio.create_task(cls._shared_read_loop(loop))
            cls._is_listening = True
            LOGGER.debug("Started shared UDP listener")

        except OSError as err:
            LOGGER.error("Failed to start shared UDP listener: %s", err)
            cls.cleanup_shared_socket()
            raise BriivError(f"Failed to start listener: {err}") from err

    @classmethod
    async def _handle_device_data(
        cls, data: bytes, json_data: dict[str, Any], addr: tuple[str, int]
    ) -> None:
        """Handle received device data and trigger callbacks."""
        # Log incoming traffic first
        cls._traffic_logger.log_incoming(data, addr, json_data)

        serial = json_data.get("serial_number")
        if not serial:
            return

        # Update device address mapping with actual device port
        cls._device_addresses[serial] = addr
        LOGGER.debug("Updated device address for %s: %s", serial, addr)

        # Update discovered devices information
        if serial not in cls._discovered_devices:
            cls._discovered_devices[serial] = {
                "host": addr[0],
                "serial_number": serial,
                "is_pro": bool(json_data.get("is_briiv_pro", 0)),
            }

        if serial in cls._instances:
            instance = cls._instances[serial]
            callback_tasks = [
                asyncio.create_task(callback(json_data))
                for callback in instance.callbacks
            ]
            if callback_tasks:
                await asyncio.gather(*callback_tasks, return_exceptions=True)

    @classmethod
    async def _shared_read_loop(cls, loop: asyncio.AbstractEventLoop) -> None:
        """Shared read loop for all instances."""
        while cls._is_listening and cls._shared_socket:
            try:
                data, addr = await loop.sock_recvfrom(cls._shared_socket, 4096)
                try:
                    json_data = json.loads(data.decode())
                    await cls._handle_device_data(data, json_data, addr)
                except json.JSONDecodeError as err:
                    # Still log raw traffic even if JSON parsing fails
                    cls._traffic_logger.log_incoming(data, addr)
                    LOGGER.warning("Error decoding JSON from %s: %s", addr[0], err)
            except (BlockingIOError, ConnectionError):
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except OSError as err:
                LOGGER.error("Socket error in shared read loop: %s", err)
                await asyncio.sleep(1)

    @classmethod
    async def discover(cls, timeout: int = 15) -> list[dict[str, Any]]:
        """Discover Briiv devices on the network using shared socket."""
        LOGGER.debug("Starting discovery with timeout %s seconds", timeout)

        # Clear previous discovery results
        cls._discovered_devices.clear()

        # Ensure we have a socket and it's properly configured
        if not cls._shared_socket:
            try:
                cls._shared_socket = cls._create_and_bind_socket()
                LOGGER.debug("Created new socket for discovery")
            except OSError as err:
                LOGGER.error("Failed to create discovery socket: %s", err)
                return []

        # Start the shared listener if not already running
        if not cls._is_listening:
            cls._shared_read_task = asyncio.create_task(
                cls._shared_read_loop(asyncio.get_running_loop())
            )
            cls._is_listening = True
            LOGGER.debug("Started shared read loop for discovery")

        try:
            # Wait for the specified timeout to collect device responses
            await asyncio.sleep(timeout)

            if not cls._discovered_devices:
                LOGGER.warning("No devices found during discovery")
                return []

            return list(cls._discovered_devices.values())

        except (TimeoutError, OSError) as err:
            LOGGER.error("Network error during discovery: %s", err)
            return []
        except RuntimeError as err:
            LOGGER.error("Runtime error during discovery: %s", err)
            return []

    async def start_listening(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start listening using the shared socket."""
        await self.start_shared_listener(loop)

    def register_callback(
        self, callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        """Register callback for data updates."""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(
        self, callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        """Remove callback from updates."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    @classmethod
    def cleanup_shared_socket(cls) -> None:
        """Clean up shared socket resources."""
        if cls._shared_socket:
            try:
                cls._shared_socket.close()
            except OSError as err:
                LOGGER.error("Error closing shared socket: %s", err)
            finally:
                cls._shared_socket = None
        cls._is_listening = False
        cls._device_addresses.clear()

    async def stop_listening(self) -> None:
        """Stop listening and clean up resources."""
        if self.serial_number in self._instances:
            del self._instances[self.serial_number]

        if not self._instances:
            if self._shared_read_task and not self._shared_read_task.done():
                self._shared_read_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._shared_read_task
            self.cleanup_shared_socket()
