"""Code for the Livisi Smart Home Controller."""
from typing import Any

from aiolivisi import AioLivisi, LivisiEvent, Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AVATAR_PORT,
    CLASSIC_PORT,
    LIVISI_DISCOVERY_NEW,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    PSS_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator


class SHC(CoordinatorEntity[LivisiDataUpdateCoordinator]):
    """Represents the Livisi Smart Home Controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        aiolivisi: AioLivisi,
    ) -> None:
        """Initialize the Livisi Smart Home Controller."""
        self._hass: HomeAssistant = hass
        self._config_entry: ConfigEntry = config_entry
        self.aiolivisi: AioLivisi = aiolivisi
        self.serial_number: str = ""
        self.controller_type: str = ""
        self.os_version: str = ""
        self.devices: list[dict[Any, Any]] = []
        self.switch_devices: list = []
        self.websocket: Websocket = Websocket(aiolivisi)
        self.is_avatar: bool = False
        self.port: str = ""
        self.rooms: dict[str, Any] = {}
        super().__init__(coordinator)
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        if bool(self.aiolivisi.livisi_connection_data) is False:
            livisi_connection_data = {
                "ip_address": self._config_entry.data["host"],
                "password": self._config_entry.data["password"],
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Set LIVISI devices."""
        shc_devices: dict[Any, Any] = self.coordinator.data
        for device in shc_devices:
            if device in self.devices:
                continue
            if device["type"] == PSS_DEVICE_TYPE:
                if device not in self.switch_devices:
                    self.switch_devices.append(device)
                    dispatcher_send(self._hass, LIVISI_DISCOVERY_NEW, device)
            self.devices.append(device)

    def on_data(self, event_data: LivisiEvent) -> None:
        """Define a handler to fire when the data is received."""
        source = event_data.source
        if event_data.onState is not None:
            device_id_state: dict = {
                "id": source,
                "state": event_data.onState,
            }
            dispatcher_send(self._hass, LIVISI_STATE_CHANGE, device_id_state)
        if event_data.isReachable is not None:
            device_id_reachability: dict = {
                "id": source.replace("/device/", ""),
                "is_reachable": event_data.isReachable,
            }
            dispatcher_send(
                self._hass, LIVISI_REACHABILITY_CHANGE, device_id_reachability
            )

    async def on_close(self) -> None:
        """Define a handler to fire when the websocket is closed."""
        for device in self.devices:
            device_id_reachability: dict = {
                "id": device.get("id"),
                "is_reachable": False,
            }
            dispatcher_send(
                self._hass, LIVISI_REACHABILITY_CHANGE, device_id_reachability
            )

        await self.websocket.connect(self.on_data, self.on_close, self.port)

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self.websocket.connect(self.on_data, self.on_close, self.port)
