"""Code to manage fetching LIVISI data API."""

import asyncio
from datetime import timedelta
from typing import Any, override

from livisi import (
    IS_REACHABLE,
    LIVISI_EVENT_STATE_CHANGED,
    LivisiConnection,
    LivisiDevice,
    LivisiException,
    LivisiWebsocketEvent,
    connect as livisi_connect,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_POLLING_DELAY,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
    STATE_PROPERTIES,
    WEBSOCKET_RECONNECT_DELAY,
)

type LivisiConfigEntry = ConfigEntry[LivisiDataUpdateCoordinator]


class LivisiDataUpdateCoordinator(DataUpdateCoordinator[list[LivisiDevice]]):
    """Class to manage fetching LIVISI data API."""

    config_entry: LivisiConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: LivisiConfigEntry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Livisi devices",
            update_interval=timedelta(seconds=DEVICE_POLLING_DELAY),
        )
        self.aiolivisi: LivisiConnection
        self.devices: set[str] = set()
        self.serial_number: str = ""
        self.controller_type: str = ""
        self.is_avatar: bool = False
        self._shutdown = False

    @override
    async def _async_update_data(self) -> list[LivisiDevice]:
        """Get device configuration from LIVISI."""
        try:
            return await self.async_get_devices()
        except LivisiException as exc:
            raise UpdateFailed("Failed to get livisi devices from controller") from exc

    def _async_dispatcher_send(
        self,
        event: str,
        source: str,
        data: Any,
        property_name: str | None = None,
    ) -> None:
        if data is not None:
            topic = f"{event}_{source}"
            if property_name is not None:
                topic = f"{topic}_{property_name}"
            async_dispatcher_send(self.hass, topic, data)

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        self.aiolivisi = await livisi_connect(
            self.config_entry.data[CONF_HOST], self.config_entry.data[CONF_PASSWORD]
        )
        controller = self.aiolivisi.controller
        self.controller_type = controller.controller_type
        self.serial_number = controller.serial_number
        self.is_avatar = controller.is_v2

    async def async_get_devices(self) -> list[LivisiDevice]:
        """Set the discovered devices list."""
        devices = await self.aiolivisi.async_get_devices()
        for device in devices:
            if device.unreachable:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE, device.id, False
                )
        return devices

    async def async_get_device_state(self, capability: str, key: str) -> Any | None:
        """Get state from livisi devices."""
        try:
            return await self.aiolivisi.async_get_value(capability, key)
        except LivisiException:
            return None

    def on_data(self, event_data: LivisiWebsocketEvent) -> None:
        """Define a handler to fire when the data is received."""
        if (
            event_data.type != LIVISI_EVENT_STATE_CHANGED
            or event_data.properties is None
        ):
            return

        self._async_dispatcher_send(
            LIVISI_REACHABILITY_CHANGE,
            event_data.source,
            event_data.properties.get(IS_REACHABLE),
        )
        for property_name in STATE_PROPERTIES:
            self._async_dispatcher_send(
                LIVISI_STATE_CHANGE,
                event_data.source,
                event_data.properties.get(property_name),
                property_name,
            )

    async def on_close(self) -> None:
        """Handle the websocket closing."""

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        while not self._shutdown:
            await self.aiolivisi.listen_for_events(self.on_data, self.on_close)
            if not self._shutdown:
                await asyncio.sleep(WEBSOCKET_RECONNECT_DELAY)

    async def async_close(self) -> None:
        """Close the connection to the Livisi controller."""
        self._shutdown = True
        await self.aiolivisi.close()
