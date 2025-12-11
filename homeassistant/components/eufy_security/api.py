"""WebSocket API client for Eufy Security (eufy-security-ws add-on)."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

from .const import MSG_EVENT, MSG_RESULT, SCHEMA_VERSION

_LOGGER = logging.getLogger(__name__)


class EufySecurityError(Exception):
    """Base exception for Eufy Security errors."""


class CannotConnectError(EufySecurityError):
    """Exception for connection failures."""


class InvalidCredentialsError(EufySecurityError):
    """Exception for invalid credentials."""


class AuthenticationError(EufySecurityError):
    """Exception for authentication failures."""


@dataclass
class Camera:
    """Representation of a Eufy Security camera."""

    serial: str
    name: str
    model: str
    station_serial: str
    hardware_version: str
    software_version: str
    last_camera_image_url: str | None
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def is_streaming(self) -> bool:
        """Return True if camera is currently streaming."""
        return self.properties.get("livestreaming", False)


@dataclass
class Station:
    """Representation of a Eufy Security station/hub."""

    serial: str
    name: str
    model: str


class EufySecurityAPI:
    """WebSocket API client for eufy-security-ws add-on."""

    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        """Initialize the API client."""
        self._session = session
        self._host = host
        self._port = port
        self._ws: ClientWebSocketResponse | None = None
        self._message_id = 0
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._listener_task: asyncio.Task[None] | None = None
        self.cameras: dict[str, Camera] = {}
        self.stations: dict[str, Station] = {}
        self._connected = False
        self._schema_version: int | None = None

    @property
    def ws_url(self) -> str:
        """Return the WebSocket URL."""
        return f"ws://{self._host}:{self._port}"

    @property
    def connected(self) -> bool:
        """Return True if connected to WebSocket server."""
        return self._connected and self._ws is not None and not self._ws.closed

    async def async_connect(self) -> None:
        """Connect to the eufy-security-ws WebSocket server."""
        try:
            self._ws = await self._session.ws_connect(
                self.ws_url,
                heartbeat=30,
            )
            self._connected = True
            self._listener_task = asyncio.create_task(self._listener())

            # Set schema version
            await self._async_set_schema_version()

            # Start listening for events
            await self._async_start_listening()

            _LOGGER.debug("Connected to eufy-security-ws at %s", self.ws_url)
        except Exception as err:
            self._connected = False
            raise CannotConnectError(
                f"Failed to connect to {self.ws_url}: {err}"
            ) from err

    async def async_disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        if self._listener_task:
            self._listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        self._connected = False

    async def _listener(self) -> None:
        """Listen for WebSocket messages."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(msg.json())
                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", msg.data)
                    break
                elif msg.type == WSMsgType.CLOSED:
                    _LOGGER.debug("WebSocket connection closed")
                    break
        except asyncio.CancelledError:
            pass
        except (ClientError, EufySecurityError) as err:
            _LOGGER.error("Error in WebSocket listener: %s", err)
        finally:
            self._connected = False

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        msg_type = data.get("type")

        if msg_type == MSG_RESULT:
            message_id = data.get("messageId")
            if message_id and message_id in self._pending:
                future = self._pending.pop(message_id)
                if data.get("success", False):
                    future.set_result(data.get("result", {}))
                else:
                    error_code = data.get("errorCode", "unknown")
                    future.set_exception(
                        EufySecurityError(f"Command failed: {error_code}")
                    )
        elif msg_type == MSG_EVENT:
            await self._handle_event(data.get("event", {}))

    async def _handle_event(self, event: dict[str, Any]) -> None:
        """Handle incoming event."""
        event_type = event.get("event")
        source = event.get("source")
        _LOGGER.debug("Received event: %s from %s", event_type, source)

        # Handle device property updates
        if event_type == "property changed":
            serial = event.get("serialNumber")
            name = event.get("name")
            value = event.get("value")
            if serial and serial in self.cameras and name:
                self.cameras[serial].properties[name] = value

    async def _async_send_command(
        self, command: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Send a command and wait for response."""
        if not self._ws or self._ws.closed:
            raise EufySecurityError("Not connected to WebSocket server")

        self._message_id += 1
        message_id = f"msg_{self._message_id}"

        message = {
            "messageId": message_id,
            "command": command,
            **kwargs,
        }

        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_event_loop().create_future()
        )
        self._pending[message_id] = future

        await self._ws.send_json(message)

        try:
            return await asyncio.wait_for(future, timeout=30)
        except TimeoutError as err:
            self._pending.pop(message_id, None)
            raise EufySecurityError(f"Command timeout: {command}") from err

    async def _async_set_schema_version(self) -> None:
        """Set the API schema version."""
        result = await self._async_send_command(
            "set_api_schema",
            schemaVersion=SCHEMA_VERSION,
        )
        self._schema_version = result.get("schemaVersion", SCHEMA_VERSION)
        _LOGGER.debug("Schema version set to %s", self._schema_version)

    async def _async_start_listening(self) -> None:
        """Start listening for events from the add-on."""
        await self._async_send_command("start_listening")

    async def async_get_driver_state(self) -> dict[str, Any]:
        """Get the current driver state including devices."""
        return await self._async_send_command("driver.get_state")

    async def async_update_device_info(self) -> None:
        """Update device information from the WebSocket server."""
        state = await self.async_get_driver_state()

        # Parse stations
        self.stations = {}
        for station_data in state.get("stations", []):
            station = Station(
                serial=station_data.get("serialNumber", ""),
                name=station_data.get("name", "Unknown"),
                model=station_data.get("model", "Unknown"),
            )
            self.stations[station.serial] = station

        # Parse devices (cameras)
        self.cameras = {}
        for device_data in state.get("devices", []):
            # Get device properties
            props = {}
            for prop in device_data.get("properties", []):
                props[prop.get("name")] = prop.get("value")

            camera = Camera(
                serial=device_data.get("serialNumber", ""),
                name=device_data.get("name", props.get("name", "Unknown")),
                model=device_data.get("model", props.get("model", "Unknown")),
                station_serial=device_data.get("stationSerialNumber", ""),
                hardware_version=props.get("hardwareVersion", ""),
                software_version=props.get("softwareVersion", ""),
                last_camera_image_url=props.get("picture"),
                properties=props,
            )
            self.cameras[camera.serial] = camera

        _LOGGER.debug(
            "Found %d cameras and %d stations",
            len(self.cameras),
            len(self.stations),
        )

    async def async_start_livestream(self, device_serial: str) -> str | None:
        """Start P2P livestream for a device and return stream URL."""
        try:
            result = await self._async_send_command(
                "device.start_livestream",
                serialNumber=device_serial,
            )
            # The stream URL is typically provided via go2rtc integration
            return result.get("url")
        except EufySecurityError as err:
            _LOGGER.warning("Failed to start livestream: %s", err)
            return None

    async def async_stop_livestream(self, device_serial: str) -> None:
        """Stop P2P livestream for a device."""
        try:
            await self._async_send_command(
                "device.stop_livestream",
                serialNumber=device_serial,
            )
        except EufySecurityError as err:
            _LOGGER.warning("Failed to stop livestream: %s", err)

    async def async_start_rtsp_livestream(self, device_serial: str) -> str | None:
        """Start RTSP livestream for a device."""
        try:
            result = await self._async_send_command(
                "device.start_rtsp_livestream",
                serialNumber=device_serial,
            )
            return result.get("url")
        except EufySecurityError as err:
            _LOGGER.warning("Failed to start RTSP livestream: %s", err)
            return None

    async def async_stop_rtsp_livestream(self, device_serial: str) -> None:
        """Stop RTSP livestream for a device."""
        try:
            await self._async_send_command(
                "device.stop_rtsp_livestream",
                serialNumber=device_serial,
            )
        except EufySecurityError as err:
            _LOGGER.warning("Failed to stop RTSP livestream: %s", err)

    async def async_get_device_properties(
        self, device_serial: str
    ) -> dict[str, Any]:
        """Get properties for a specific device."""
        try:
            result = await self._async_send_command(
                "device.get_properties",
                serialNumber=device_serial,
            )
            return result.get("properties", {})
        except EufySecurityError as err:
            _LOGGER.warning("Failed to get device properties: %s", err)
            return {}


async def async_connect(
    host: str, port: int, session: ClientSession
) -> EufySecurityAPI:
    """Connect to eufy-security-ws and return an API client."""
    api = EufySecurityAPI(session, host, port)
    await api.async_connect()
    await api.async_update_device_info()
    return api
