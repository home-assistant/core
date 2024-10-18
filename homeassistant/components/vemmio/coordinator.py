"""Vemmio coordinator."""

from __future__ import annotations

from collections.abc import Iterable

from vemmio_client import (
    Client,
    DeviceConnectionError,
    DeviceNode,
    Event,
    GatewayReport,
    switch,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class VemmioData:
    """Class to hold Vemmio data."""

    def __init__(self, nodes: Iterable[DeviceNode]) -> None:
        """Initialize the data."""
        self.nodes = nodes
        self.switch = dict[bytes, bool]()

    def is_on(self, device_id: bytes) -> bool:
        """Return the switch state."""
        return self.switch.get(device_id, False)

    def set_switch(self, device_id: bytes, state: bool):
        """Set the switch state."""
        self.switch[device_id] = state


class VemmioDataUpdateCoordinator(DataUpdateCoordinator[VemmioData]):
    """Class to manage fetching Vemmio data."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the coordinator."""

        self.client = Client(host, port, async_get_clientsession(hass))
        self.client.message_handler = self.message_handler
        self.client.event_handler = self.event_handler

        super().__init__(hass, LOGGER, name=DOMAIN)

    async def _async_update_data(self) -> VemmioData:
        """Fetch data from the device."""

        LOGGER.debug("crd: _async_update_data")
        await self.connect()
        return await self.get_nodes()

    async def connect(self):
        """Connect to the device."""

        LOGGER.debug("crd: connect")
        try:
            await self.client.connect()
        except Exception as err:
            raise UpdateFailed from err

    async def get_nodes(self) -> VemmioData:
        """Get nodes from the device."""

        LOGGER.debug("crd: get_nodes")
        try:
            nodes = await self.client.get_nodes()
            return VemmioData(nodes)
        except DeviceConnectionError as err:
            raise ConfigEntryNotReady from err

    @callback
    def message_handler(self, r: GatewayReport):
        """Handle messages from the client."""

        LOGGER.debug("crd: received report")
        if r.device:
            LOGGER.debug("crd: received device report")
            if r.device.switch:
                device_id = r.device.metadata.mqtt.device_id
                state = switch.is_on(r.device.switch)
                LOGGER.debug(
                    "crd: received switch report, id=%s, state=%s", device_id, state
                )
                self.data.set_switch(device_id, state)
                self.async_set_updated_data(self.data)

    @callback
    def event_handler(self, e: Event):
        """Handle events from the client."""

        LOGGER.debug("crd: received event=%s", e)
        match e:
            case Event.CONN_CLOSED:
                self.hass.async_create_task(self._disconnected())

    async def _disconnected(self) -> None:
        LOGGER.debug("crd: disconnected")
        if not self.hass.is_stopping:
            await self.async_request_refresh()
