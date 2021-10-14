"""The lookin integration protocol."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Final

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    DEVICE_INFO_URL,
    DEVICES_INFO_URL,
    INFO_URL,
    METEO_SENSOR_URL,
    SEND_IR_COMMAND,
    UPDATE_CLIMATE_URL,
)
from .error import DeviceNotFound, NoUsableService
from .models import Climate, Device, MeteoSensor, Remote

DEVICE_TO_CODE: Final = {
    "tv": "1",
    "media": "2",
    "light": "3",
    "humidifier": "4",
    "air_purifier": "5",
    "vacuum": "6",
    "fan": "7",
    "climate_control": "EF",
}

COMMAND_TO_CODE: Final = {
    "power": "01",
    "poweron": "02",
    "poweroff": "03",
    "mode": "04",
    "mute": "05",
    "volup": "06",
    "voldown": "07",
    "chup": "08",
    "chdown": "09",
    "swing": "0A",
    "speed": "0B",
    "cursor": "0C",
    "menu": "0D",
}


async def validate_response(response: ClientResponse) -> None:
    if response.status not in (200, 201, 204):
        raise NoUsableService


class LookinSubscriptions:
    """Store Lookin subscriptions."""

    def __init__(self):
        """Init and store callbacks."""
        self._callbacks = {}
        self.last_message_time = 0

    def subscribe(self, device_id, callback):
        """Subscribe to lookin updates."""
        self._callbacks.setdefault(device_id, []).append(callback)

    def unsubscribe(self, device_id, callback):
        """Unsubscribe from lookin updates."""
        self._callbacks[device_id].remove(callback)

    def notify(self, json_msg):
        """Notify subscribers of an update."""
        if json_msg.get("s") != 200:
            return

        topic = json_msg["t"].split("/")
        device_id = topic[1]

        for callback in self._callbacks.get(device_id, []):
            callback(json_msg["b"])


INIT_PUSH_MESSAGE = "\n"
LOOKIN_PORT = 6633


class LookinUDPProtocol:
    """Implements Lookin UDP Protocol."""

    def __init__(self, loop, subscriptions):
        """Create Lookin UDP Protocol."""
        self.loop = loop
        self.subscriptions = subscriptions
        self.transport = None
        self.keep_alive = None

    def connection_made(self, transport):
        """Connect or reconnect to the device."""
        self.transport = transport
        if self.keep_alive:
            self.keep_alive.cancel()
            self.keep_alive = None
        self.send_keep_alive()

    def send_keep_alive(self):
        """Send a keep alive every 60 seconds per the protocol."""
        self.transport.sendto(INIT_PUSH_MESSAGE)
        self.keep_alive = self.loop.call_later(60, self.send_keep_alive)

    def datagram_received(self, data, addr):
        """Process incoming state changes."""
        self.subscriptions.notify(json.loads(data.decode()[:-1]))

    def error_received(self, exc):
        """Ignore errors."""
        return

    def connection_lost(self, exc):
        """Ignore connection lost."""
        return

    def stop(self):
        """Stop the client."""
        if self.transport:
            self.transport.close()


async def start_lookin_udp(host_ip_addr, subscriptions):
    """Create the socket and protocol."""
    loop = asyncio.get_event_loop()

    _, protocol = await loop.create_datagram_endpoint(
        lambda: LookinUDPProtocol(loop, subscriptions),
        remote_addr=(host_ip_addr, LOOKIN_PORT),
    )
    return protocol.stop


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
