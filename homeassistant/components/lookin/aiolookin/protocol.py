"""The lookin integration protocol."""
from __future__ import annotations

import asyncio
import contextlib
import json
import socket
from typing import Any, Callable, Final

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    COMMAND_TO_CODE,
    DEVICE_INFO_URL,
    DEVICES_INFO_URL,
    INFO_URL,
    METEO_SENSOR_URL,
    SEND_IR_COMMAND,
    UPDATE_CLIMATE_URL,
)
from .error import DeviceNotFound, NoUsableService
from .models import Climate, Device, MeteoSensor, Remote

LOOKIN_PORT: Final = 61201


async def validate_response(response: ClientResponse) -> None:
    if response.status not in (200, 201, 204):
        raise NoUsableService


class LookinUDPSubscriptions:
    """Store Lookin subscriptions."""

    def __init__(self) -> None:
        """Init and store callbacks."""
        self._callbacks: dict[str, list[Callable]] = {}

    def subscribe(self, device_id: str, callback: Callable) -> Callable:
        """Subscribe to lookin updates."""
        self._callbacks.setdefault(device_id, []).append(callback)

        def _remove_call(*_):
            self._callbacks[device_id].remove(callback)

        return _remove_call

    def notify(self, msg: dict[str, Any]) -> None:
        """Notify subscribers of an update."""
        device_id = msg["device_id"]
        for callback in self._callbacks.get(device_id, []):
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

    def connection_made(self, transport):
        """Connect or reconnect to the device."""
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Any) -> None:
        """Process incoming state changes."""
        # LOOK.in:Updated!{device id}:{sensor id}:{event id}:{value}
        # LOOK.in:Updated!{device id}:{service name}:{value}
        try:
            content = data.decode()
            if not content.startswith("LOOK.in:Updated!"):
                return
            _, msg = content.split("!")
            contents = msg.split(":")
            if len(contents) == 4:
                self.subscriptions.notify(
                    {
                        "device_id": contents[0],
                        "sensor_id": contents[1],
                        "event_id": contents[2],
                        "value": contents[3],
                    }
                )
                return
            self.subscriptions.notify(
                {
                    "device_id": contents[0],
                    "service_name": contents[1],
                    "value": contents[2],
                }
            )
        except (KeyError, ValueError, UnicodeDecodeError):
            pass

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
        try:
            response = await self._session.get(url=INFO_URL.format(host=self._host))
        except ClientError:
            raise DeviceNotFound

        async with response:
            await validate_response(response)
            payload = await response.json()

        return Device(_data=payload)

    async def update_device_name(self, name: str) -> None:
        try:
            response = await self._session.post(
                url=INFO_URL.format(host=self._host), data=json.dumps({"name": name})
            )
        except ClientError:
            raise DeviceNotFound

        async with response:
            await validate_response(response)

    async def get_meteo_sensor(self) -> MeteoSensor:
        try:
            response = await self._session.get(
                url=METEO_SENSOR_URL.format(host=self._host)
            )
        except ClientError:
            raise DeviceNotFound

        async with response:
            await validate_response(response)
            payload = await response.json()

        return MeteoSensor(_data=payload)

    async def get_devices(self) -> list[dict[str, Any]]:
        try:
            response = await self._session.get(
                url=DEVICES_INFO_URL.format(host=self._host)
            )
        except ClientError:
            raise DeviceNotFound

        async with response:
            await validate_response(response)
            payload = await response.json()

        return payload

    async def get_device(self, uuid: str) -> dict[str, Any]:
        try:
            response = await self._session.get(
                url=DEVICE_INFO_URL.format(host=self._host, uuid=uuid)
            )
        except ClientError:
            raise DeviceNotFound

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

        try:
            await self._session.get(
                url=SEND_IR_COMMAND.format(
                    host=self._host, uuid=uuid, command=code, signal=signal
                )
            )
        except ClientError:
            raise DeviceNotFound

    async def update_conditioner(self, extra: str, status: str) -> None:
        try:
            await self._session.get(
                url=UPDATE_CLIMATE_URL.format(
                    host=self._host, extra=extra, status=status
                )
            )
        except ClientError:
            raise DeviceNotFound

        await asyncio.sleep(1)
