"""Code for the Livisi Smart Home Controller."""
import asyncio
from collections.abc import Callable
import json
from typing import Any

from aiolivisi import AioLivisi, Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import (
    AVATAR_PORT,
    CLASSIC_PORT,
    DEVICE_POLLING_DELAY,
    PSS_DEVICE_TYPE,
    SWITCH_PLATFORM,
)


class SHC:
    """Represents the Livisi Smart Home Controller."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Livisi Smart Home Controller."""
        self._hass: HomeAssistant = hass
        self._config_entry: ConfigEntry = config_entry
        self.aiolivisi: AioLivisi = None
        self._serial_number: str = ""
        self._controller_type: str = ""
        self._os_version: str = ""
        self._devices: list[dict[str, Any]] = []
        self.included_devices: list = []
        self._switch_devices: list = []
        self._websocket: Websocket = Websocket()
        self._is_avatar: bool = False
        self._port: str = ""
        self._rooms: dict[str, Any] = {}
        self._subscribers: dict[str, Callable] = {}

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        return self._serial_number

    @serial_number.setter
    def serial_number(self, new_value: str):
        self._serial_number = new_value

    @property
    def controller_type(self) -> str:
        """Return the controller type."""
        return self._controller_type

    @controller_type.setter
    def controller_type(self, new_value):
        self._controller_type = new_value

    @property
    def os_version(self) -> str:
        """Return the os version of the box."""
        return self._os_version

    @os_version.setter
    def os_version(self, new_value: str):
        self._os_version = new_value

    @property
    def host(self):
        """Return ip address of the LIVISI Smart Home Controller."""
        return self._config_entry.data["host"]

    @property
    def devices(self):
        """Return a list of all devices."""
        return self._devices

    @property
    def switch_devices(self):
        """Return a list of all switch devices."""
        return self._switch_devices

    @property
    def websocket(self) -> Websocket:
        """Return the websocket."""
        return self._websocket

    @property
    def is_avatar(self):
        """Return the controller type."""
        return self._is_avatar

    @property
    def rooms(self):
        """Return the LIVISI rooms."""
        return self._rooms

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        web_session = aiohttp_client.async_get_clientsession(self._hass)
        self.aiolivisi = AioLivisi.get_instance()
        self.aiolivisi.web_session = web_session
        if bool(self.aiolivisi.livisi_connection_data) is False:
            livisi_connection_data = {
                "ip_address": self._config_entry.data["host"],
                "password": self._config_entry.data["password"],
            }

            await self.aiolivisi.async_set_token(
                livisi_connection_data=livisi_connection_data
            )
        controller_info = await self.aiolivisi.async_get_controller()
        if bool(controller_info) is False:
            controller_info = await self.aiolivisi.async_get_controller()

        controller_data = controller_info
        if controller_data.get("controllerType") == "Avatar":
            self._port = AVATAR_PORT
            self._is_avatar = True
        else:
            self._port = CLASSIC_PORT
            self._is_avatar = False
        self.serial_number = controller_data.get("serialNumber")
        self.controller_type = controller_data.get("controllerType")
        self.os_version = controller_data.get("osVersion")
        self._hass.loop.create_task(self.async_poll_devices())

    def register_new_device_callback(
        self, device_type: str, add_device_callback: Callable
    ):
        """Register new device callback."""
        self._subscribers[device_type] = add_device_callback

    async def async_set_devices(self) -> None:
        """Set the discovered devices list."""
        shc_devices = await self.aiolivisi.async_get_devices()
        if bool(shc_devices) is False:
            shc_devices = await self.aiolivisi.async_get_devices()

        for device in shc_devices:
            if device in self._devices:
                continue
            if device.get("type") == PSS_DEVICE_TYPE:
                if device not in self._switch_devices:
                    self._switch_devices.append(device)
                    if SWITCH_PLATFORM in self._subscribers:
                        async_add_switch: Callable = self._subscribers[SWITCH_PLATFORM]
                        await async_add_switch(device)
            self._devices.append(device)

    async def async_poll_devices(self) -> None:
        """Get the devices from the LIVISI Smart Home Controller."""
        while True:
            try:
                await asyncio.sleep(DEVICE_POLLING_DELAY)
                await self.async_set_devices()
            except Exception:  # pylint: disable=broad-except
                await asyncio.sleep(DEVICE_POLLING_DELAY)

    async def async_get_pss_state(self, capability):
        """Set the PSS state."""
        response = await self.aiolivisi.async_get_pss_state(capability[1:])
        if response is None:
            return
        on_state = response.get("onState")
        return on_state.get("value")

    async def async_set_all_rooms(self):
        """Set the room list."""
        response = await self.aiolivisi.async_get_all_rooms()

        for available_room in response:
            self._rooms[available_room.get("id")] = available_room.get("config").get(
                "name"
            )

    def on_data(self, event_data: str) -> None:
        """Define a handler to fire when the data is received."""
        json_data = json.loads(event_data)
        for device in self.included_devices:
            source = json_data.get("source")
            if device.capability_id == source:
                device.update_states(json_data.get("properties"))
                continue
            if device.unique_id in source:
                reachability = json_data.get("properties")
                is_reachable: bool = reachability.get("isReachable")
                device.update_reachability(is_reachable)
            elif device.available is False:
                device.update_reachability(True)

    async def on_close(self) -> None:
        """Define a handler to fire when the websocket is closed."""
        for device in self.included_devices:
            device.update_reachability(False)

        await self._websocket.connect(self.on_data, self.on_close, self._port)

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self._websocket.connect(self.on_data, self.on_close, self._port)
