"""Code to manage fetching LIVISI data API."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import ClientConnectorError
from aiolivisi import AioLivisi, LivisiEvent, Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AVATAR,
    AVATAR_PORT,
    CLASSIC_PORT,
    CONF_HOST,
    CONF_PASSWORD,
    DEVICE_POLLING_DELAY,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
)


class LivisiDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching LIVISI data API."""

    config_entry: ConfigEntry

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
        self.config_entry = config_entry
        self.hass = hass
        self.aiolivisi = aiolivisi
        self.websocket = Websocket(aiolivisi)
        self.devices: set[str] = set()
        self.rooms: dict[str, Any] = {}
        self.serial_number: str = ""
        self.controller_type: str = ""
        self.is_avatar: bool = False
        self.port: int = 0

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Get device configuration from LIVISI."""
        try:
            return await self.async_get_devices()
        except ClientConnectorError as exc:
            raise UpdateFailed("Failed to get LIVISI the devices") from exc

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        if not self.aiolivisi.livisi_connection_data:
            livisi_connection_data = {
                "ip_address": self.config_entry.data[CONF_HOST],
                "password": self.config_entry.data[CONF_PASSWORD],
            }

            await self.aiolivisi.async_set_token(
                livisi_connection_data=livisi_connection_data
            )
        controller_data = await self.aiolivisi.async_get_controller()
        if (controller_type := controller_data["controllerType"]) == AVATAR:
            self.port = AVATAR_PORT
            self.is_avatar = True
        else:
            self.port = CLASSIC_PORT
            self.is_avatar = False
        self.controller_type = controller_type
        self.serial_number = controller_data["serialNumber"]

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Set the discovered devices list."""
        return await self.aiolivisi.async_get_devices()

    async def async_get_pss_state(self, capability: str) -> bool | None:
        """Set the PSS state."""
        response: dict[str, Any] | None = await self.aiolivisi.async_get_device_state(
            capability[1:]
        )
        if response is None:
            return None
        on_state = response["onState"]
        return on_state["value"]

    async def async_get_vrcc_target_temperature(self, capability: str) -> float | None:
        """Get the target temperature of the climate device."""
        response: dict[str, Any] | None = await self.aiolivisi.async_get_device_state(
            capability[1:]
        )
        if response is None:
            return None
        if self.is_avatar:
            return response["setpointTemperature"]["value"]
        return response["pointTemperature"]["value"]

    async def async_get_vrcc_temperature(self, capability: str) -> float | None:
        """Get the temperature of the climate device."""
        response: dict[str, Any] | None = await self.aiolivisi.async_get_device_state(
            capability[1:]
        )
        if response is None:
            return None
        return response["temperature"]["value"]

    async def async_get_vrcc_humidity(self, capability: str) -> int | None:
        """Get the humidity of the climate device."""
        response: dict[str, Any] | None = await self.aiolivisi.async_get_device_state(
            capability[1:]
        )
        if response is None:
            return None
        return response["humidity"]["value"]

    async def async_set_all_rooms(self) -> None:
        """Set the room list."""
        response: list[dict[str, Any]] = await self.aiolivisi.async_get_all_rooms()

        for available_room in response:
            available_room_config: dict[str, Any] = available_room["config"]
            self.rooms[available_room["id"]] = available_room_config["name"]

    def on_data(self, event_data: LivisiEvent) -> None:
        """Define a handler to fire when the data is received."""
        if event_data.onState is not None:
            async_dispatcher_send(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{event_data.source}",
                event_data.onState,
            )
        if event_data.vrccData is not None:
            async_dispatcher_send(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{event_data.source}",
                event_data.vrccData,
            )
        if event_data.isReachable is not None:
            async_dispatcher_send(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{event_data.source}",
                event_data.isReachable,
            )

    async def on_close(self) -> None:
        """Define a handler to fire when the websocket is closed."""
        for device_id in self.devices:
            is_reachable: bool = False
            async_dispatcher_send(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{device_id}",
                is_reachable,
            )

        await self.websocket.connect(self.on_data, self.on_close, self.port)

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self.websocket.connect(self.on_data, self.on_close, self.port)
