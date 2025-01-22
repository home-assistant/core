"""API for communicating with Briiv air purifiers over UDP."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
import json
import socket
from typing import Any, ClassVar

from homeassistant.core import _LOGGER
from homeassistant.exceptions import HomeAssistantError


class BriivError(HomeAssistantError):
    """Briiv base error."""


class BriivCallbackError(BriivError):
    """Briiv callback error."""


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
        _LOGGER.debug("Created command: %s", cmd)
        return cmd

    @staticmethod
    def power_command(
        serial_number: str,
        state: bool,
    ) -> dict[str, Any]:
        """Create power on/off command."""
        _LOGGER.debug(
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
        _LOGGER.debug(
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
        _LOGGER.debug(
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
            _LOGGER.debug("Registered device instance for %s", serial_number)

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
                _LOGGER.debug(
                    "Sending command to specific device at %s: %s",
                    dest_addr,
                    data.decode(),
                )
                await asyncio.get_running_loop().sock_sendto(
                    self._shared_socket, data, dest_addr
                )
            else:
                # Fall back to broadcast if device address unknown
                _LOGGER.debug(
                    "Device address unknown, broadcasting command: %s", data.decode()
                )
                await asyncio.get_running_loop().sock_sendto(
                    self._shared_socket, data, ("255.255.255.255", self.port)
                )

        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to send command: %s", err)
            raise BriivError(f"Failed to send command: {err}") from err

    async def set_power(self, state: bool) -> None:
        """Set power state."""
        _LOGGER.debug("Setting power state to: %s", state)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.power_command(self.serial_number, state)
        await self.send_command(command)
        _LOGGER.debug("Power command sent: %s", command)

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed."""
        _LOGGER.debug("Setting fan speed to: %s", speed)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.fan_speed_command(self.serial_number, speed)
        await self.send_command(command)
        _LOGGER.debug("Fan speed command sent: %s", command)

    async def set_boost(self, boost: bool) -> None:
        """Set boost mode."""
        _LOGGER.debug("Setting boost mode to: %s", boost)
        if not self.serial_number:
            raise BriivError("Serial number not set")
        command = BriivCommands.boost_command(self.serial_number, boost)
        await self.send_command(command)
        _LOGGER.debug("Boost command sent: %s", command)

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
            _LOGGER.debug("Socket created and bound successfully")

            cls._shared_read_task = asyncio.create_task(cls._shared_read_loop(loop))
            cls._is_listening = True
            _LOGGER.debug("Started shared UDP listener")

        except OSError as err:
            _LOGGER.error("Failed to start shared UDP listener: %s", err)
            cls.cleanup_shared_socket()
            raise BriivError(f"Failed to start listener: {err}") from err

    @classmethod
    async def _handle_device_data(
        cls, json_data: dict[str, Any], addr: tuple[str, int]
    ) -> None:
        """Handle received device data and trigger callbacks."""
        serial = json_data.get("serial_number")
        if not serial:
            return

        # Update device address mapping with actual device port
        cls._device_addresses[serial] = addr
        _LOGGER.debug("Updated device address for %s: %s", serial, addr)

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
                    await cls._handle_device_data(json_data, addr)
                except json.JSONDecodeError as err:
                    _LOGGER.warning("Error decoding JSON from %s: %s", addr[0], err)
            except (BlockingIOError, ConnectionError):
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except OSError as err:
                _LOGGER.error("Socket error in shared read loop: %s", err)
                await asyncio.sleep(1)

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

    @staticmethod
    async def discover(timeout: int = 15) -> list[dict[str, Any]]:
        """Discover Briiv devices on the network."""
        devices: list[dict[str, Any]] = []
        _LOGGER.debug("Starting discovery with timeout %s seconds", timeout)

        async def process_device_data(
            json_data: dict[str, Any], addr: tuple[str, int]
        ) -> None:
            """Process device data from discovery."""
            if "serial_number" not in json_data:
                return

            device_info = {
                "host": addr[0],
                "serial_number": json_data["serial_number"],
                "is_pro": bool(json_data.get("is_briiv_pro", 0)),
            }

            if not any(
                d["serial_number"] == device_info["serial_number"] for d in devices
            ):
                _LOGGER.info(
                    "Found Briiv device %s at %s",
                    json_data["serial_number"],
                    addr[0],
                )
                devices.append(device_info)

        sock = None
        try:
            sock = BriivAPI._setup_discovery_socket()
            await BriivAPI._discover_devices(sock, timeout, process_device_data)
        except OSError as err:
            _LOGGER.error("Discovery socket error: %s", err)
            raise BriivError(f"Discovery failed: {err}") from err
        finally:
            if sock:
                sock.close()

        return devices

    @staticmethod
    def _setup_discovery_socket() -> socket.socket:
        """Set up socket for discovery."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

        try:
            sock.bind(("0.0.0.0", 3334))
        except OSError:
            try:
                sock.bind(("127.0.0.1", 3334))
            except OSError as err:
                raise BriivError(f"Failed to bind discovery socket: {err}") from err

        sock.setblocking(False)
        _LOGGER.debug("Discovery socket bound successfully")
        return sock

    @staticmethod
    async def _discover_devices(
        sock: socket.socket,
        timeout: int,
        callback: Callable[[dict[str, Any], tuple[str, int]], Awaitable[None]],
    ) -> None:
        """Discover devices using the provided socket."""
        loop = asyncio.get_running_loop()
        end_time = loop.time() + timeout

        while loop.time() < end_time:
            try:
                data, addr = await loop.sock_recvfrom(sock, 4096)
                try:
                    json_data = json.loads(data.decode())
                    await callback(json_data, addr)
                except json.JSONDecodeError as err:
                    _LOGGER.debug("Invalid JSON received from %s: %s", addr[0], err)
            except (TimeoutError, BlockingIOError):
                await asyncio.sleep(0.1)

    @classmethod
    def cleanup_shared_socket(cls) -> None:
        """Clean up shared socket resources."""
        if cls._shared_socket:
            try:
                cls._shared_socket.close()
            except OSError as err:
                _LOGGER.error("Error closing shared socket: %s", err)
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
