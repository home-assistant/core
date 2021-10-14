"""The lookin integration protocol."""
from __future__ import annotations

import asyncio
import contextlib
from enum import Enum
import json
import logging
import socket
from typing import Any, Callable, Final

from aiohttp import ClientResponse, ClientSession, ClientTimeout

from .const import (
    COMMAND_TO_CODE,
    DEVICE_INFO_URL,
    DEVICES_INFO_URL,
    INFO_URL,
    METEO_SENSOR_URL,
    SEND_IR_COMMAND,
    UPDATE_CLIMATE_URL,
)
from .error import NoUsableService
from .models import Climate, Device, MeteoSensor, Remote

LOOKIN_PORT: Final = 61201

CLIENT_TIMEOUTS: Final = ClientTimeout(total=9, connect=8, sock_connect=7, sock_read=7)

LOGGER = logging.getLogger(__name__)


class SensorID(Enum):
    IR = "87"
    Meteo = "FE"


async def validate_response(response: ClientResponse) -> None:
    if response.status not in (200, 201, 204):
        raise NoUsableService


class LookinUDPSubscriptions:
    """Store Lookin subscriptions."""

    def __init__(self) -> None:
        """Init and store callbacks."""
        self._sensor_callbacks: dict[tuple[str, str, str | None], list[Callable]] = {}
        self._service_callbacks: dict[tuple[str, str], list[Callable]] = {}

    def subscribe_sensor(
        self, device_id: str, sensor_id: SensorID, uuid: str | None, callback: Callable
    ) -> Callable:
        """Subscribe to lookin sensor updates."""
        self._sensor_callbacks.setdefault(
            (device_id, sensor_id.value, uuid), []
        ).append(callback)

        def _remove_call(*_: Any):
            self._sensor_callbacks[(device_id, sensor_id.value, uuid)].remove(callback)

        return _remove_call

    def notify_sensor(self, msg: dict[str, Any]) -> None:
        """Notify subscribers of a sensor update."""
        device_id: str = msg["device_id"]
        sensor_id: str = msg["sensor_id"]
        uuid: str | None = msg.get("uuid")
        LOGGER.debug("Received sensor push updates: %s", msg)
        for callback in self._sensor_callbacks.get((device_id, sensor_id, uuid), []):
            callback(msg)

    def subscribe_service(
        self, device_id: str, service_name: str, callback: Callable
    ) -> Callable:
        """Subscribe to lookin service updates."""
        self._service_callbacks.setdefault((device_id, service_name), []).append(
            callback
        )

        def _remove_call(*_: Any):
            self._service_callbacks[(device_id, service_name)].remove(callback)

        return _remove_call

    def notify_service(self, msg: dict[str, Any]) -> None:
        """Notify subscribers of a service update."""
        LOGGER.debug("Received service push updates: %s", msg)
        device_id: str = msg["device_id"]
        service_name: str = msg["service_name"]
        for callback in self._service_callbacks.get((device_id, service_name), []):
            callback(msg)


class LookinUDPProtocol:
    """Implements Lookin UDP Protocol."""

    def __init__(
        self, loop: asyncio.AbstractEventLoop, subscriptions: LookinUDPSubscriptions
    ) -> None:
        """Create Lookin UDP Protocol."""
        self.loop = loop
        self.subscriptions = subscriptions
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Connect or reconnect to the device."""
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Any) -> None:
        """Process incoming state changes."""
        content = data.decode()
        if not content.startswith("LOOK.in:Updated!"):
            return
        _, msg = content.split("!")
        contents = msg.split(":")
        update: dict[str, str] = {"device_id": contents[0]}
        if len(contents) == 3:
            # LOOK.in:Updated!{device id}:{service name}:{value}
            update["service_name"] = contents[1]
            update["value"] = contents[2]
            self.subscriptions.notify_service(update)
            return
        # LOOK.in:Updated!{device id}:{sensor id}:{event id}:{value}
        sensor_id = update["sensor_id"] = contents[1]
        update["event_id"] = contents[2]
        if sensor_id == SensorID.IR.value:
            update["uuid"] = contents[3][:4]
            update["value"] = contents[3][4:]
        else:
            update["value"] = contents[3]
        self.subscriptions.notify_sensor(update)

    def error_received(self, exc: Exception) -> None:
        """Ignore errors."""
        return

    def connection_lost(self, exc: Exception) -> None:
        """Ignore connection lost."""
        return

    def stop(self) -> None:
        """Stop the client."""
        if self.transport:
            self.transport.close()


def _create_udp_socket() -> socket.socket:
    """Create a udp listener socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with contextlib.suppress(Exception):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", LOOKIN_PORT))
    sock.setblocking(False)
    return sock


async def start_lookin_udp(subscriptions: LookinUDPSubscriptions) -> Callable:
    """Create the socket and protocol."""
    loop = asyncio.get_event_loop()
    _, protocol = await loop.create_datagram_endpoint(
        lambda: LookinUDPProtocol(loop, subscriptions),  # type: ignore
        sock=_create_udp_socket(),
    )
    return protocol.stop  # type: ignore


class LookInHttpProtocol:
    def __init__(self, host: str, session: ClientSession) -> None:
        self._host = host
        self._session = session

    async def get_info(self) -> Device:
        response = await self._session.get(
            url=INFO_URL.format(host=self._host), timeout=CLIENT_TIMEOUTS
        )
        async with response:
            await validate_response(response)
            payload = await response.json()

        return Device(_data=payload)

    async def update_device_name(self, name: str) -> None:
        response = await self._session.post(
            url=INFO_URL.format(host=self._host), data=json.dumps({"name": name})
        )
        async with response:
            await validate_response(response)

    async def get_meteo_sensor(self) -> MeteoSensor:
        response = await self._session.get(
            url=METEO_SENSOR_URL.format(host=self._host), timeout=CLIENT_TIMEOUTS
        )

        async with response:
            await validate_response(response)
            payload = await response.json()

        return MeteoSensor(_data=payload)

    async def get_devices(self) -> list[dict[str, Any]]:
        response = await self._session.get(
            url=DEVICES_INFO_URL.format(host=self._host), timeout=CLIENT_TIMEOUTS
        )

        async with response:
            await validate_response(response)
            payload = await response.json()

        return payload

    async def get_device(self, uuid: str) -> dict[str, Any]:
        response = await self._session.get(
            url=DEVICE_INFO_URL.format(host=self._host, uuid=uuid),
            timeout=CLIENT_TIMEOUTS,
        )

        async with response:
            await validate_response(response)
            payload = await response.json()

        return payload

    async def get_conditioner(self, uuid: str) -> Climate:
        payload = await self.get_device(uuid=uuid)
        return Climate(_data=payload)

    async def get_remote(self, uuid: str) -> Remote:
        payload = await self.get_device(uuid=uuid)
        return Remote(_data=payload)

    async def send_command(self, uuid: str, command: str, signal: str) -> None:
        if not (code := COMMAND_TO_CODE.get(command)):
            return

        await self._session.get(
            url=SEND_IR_COMMAND.format(
                host=self._host, uuid=uuid, command=code, signal=signal
            ),
            timeout=CLIENT_TIMEOUTS,
        )

    async def update_conditioner(self, extra: str, status: str) -> None:
        await self._session.get(
            url=UPDATE_CLIMATE_URL.format(host=self._host, extra=extra, status=status),
            timeout=CLIENT_TIMEOUTS,
        )
