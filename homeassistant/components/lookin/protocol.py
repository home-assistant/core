"""The lookin integration protocol --- TODO: Make this a PyPi."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Final

from aiohttp import ClientError

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

if TYPE_CHECKING:
    from aiohttp import ClientResponse, ClientSession

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
