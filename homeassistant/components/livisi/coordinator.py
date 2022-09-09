"""Code to manage fetching LIVISI data API."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiolivisi import AioLivisi, LivisiEvent, Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    AVATAR_PORT,
    CLASSIC_PORT,
    DEVICE_POLLING_DELAY,
    LIVISI_DISCOVERY_NEW,
    LOGGER,
    PSS_DEVICE_TYPE,
)


class LivisiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching LIVISI data API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, aiolivisi: AioLivisi
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Livisi devices",
            update_interval=timedelta(seconds=DEVICE_POLLING_DELAY),
        )
        self.config_entry: ConfigEntry = config_entry
        self.hass: HomeAssistant = hass
        self.aiolivisi: AioLivisi = aiolivisi
        self.websocket: Websocket = Websocket(aiolivisi)
        self.devices: list[dict[Any, Any]] = []
        self.switch_devices: list = []
        self.rooms: dict[str, Any] = {}
        self.serial_number: str | None
        self.controller_type: str | None
        self.os_version: str | None
        self.is_avatar: bool = False
        self.port: str = ""

    async def _async_update_data(self):
        """Set device list."""
        shc_devices: dict[Any, Any] = await self.async_get_devices()
        for device in shc_devices:
            if device in self.devices:
                continue
            if device["type"] == PSS_DEVICE_TYPE:
                if device not in self.switch_devices:
                    self.switch_devices.append(device)
                    async_dispatcher_send(self.hass, LIVISI_DISCOVERY_NEW, device)
            self.devices.append(device)

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        if bool(self.aiolivisi.livisi_connection_data) is False:
            livisi_connection_data = {
                "ip_address": self.config_entry.data["host"],
                "password": self.config_entry.data["password"],
            }

            await self.aiolivisi.async_set_token(
                livisi_connection_data=livisi_connection_data
            )
        controller_info = await self.aiolivisi.async_get_controller()

        controller_data = controller_info
        if controller_data.get("controllerType") == "Avatar":
            self.port = AVATAR_PORT
            self.is_avatar = True
        else:
            self.port = CLASSIC_PORT
            self.is_avatar = False
        self.serial_number = controller_data.get("serialNumber")
        self.controller_type = controller_data.get("controllerType")
        self.os_version = controller_data.get("osVersion")

    async def async_get_devices(self) -> list:
        """Set the discovered devices list."""
        shc_devices = await self.aiolivisi.async_get_devices()
        if bool(shc_devices) is False:
            shc_devices = await self.aiolivisi.async_get_devices()
        return shc_devices

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
            self.rooms[available_room.get("id")] = available_room.get("config").get(
                "name"
            )

    def on_data(self, event_data: LivisiEvent) -> None:
        """Define a handler to fire when the data is received."""
        source = event_data.source
        if event_data.onState is not None:
            device_id_state: dict = {
                "id": source,
                "state": event_data.onState,
            }
            self.async_set_updated_data(device_id_state)
        if event_data.isReachable is not None:
            device_id_reachability: dict = {
                "id": source.replace("/device/", ""),
                "is_reachable": event_data.isReachable,
            }
            self.async_set_updated_data(device_id_reachability)

    async def on_close(self) -> None:
        """Define a handler to fire when the websocket is closed."""
        for device in self.devices:
            device_id_reachability: dict = {
                "id": device.get("id"),
                "is_reachable": False,
            }
            self.async_set_updated_data(device_id_reachability)

        await self.websocket.connect(self.on_data, self.on_close, self.port)

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self.websocket.connect(self.on_data, self.on_close, self.port)
