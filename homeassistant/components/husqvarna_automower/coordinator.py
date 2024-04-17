"""Data UpdateCoordinator for the Husqvarna Automower integration."""

import asyncio
from datetime import timedelta
import logging

from aioautomower.exceptions import ApiException, HusqvarnaWSServerHandshakeError
from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAX_WS_RECONNECT_TIME = 600
SCAN_INTERVAL = timedelta(minutes=8)


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, MowerAttributes]]):
    """Class to manage fetching Husqvarna data."""

    def __init__(
        self, hass: HomeAssistant, api: AutomowerSession, entry: ConfigEntry
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

        self.ws_connected: bool = False

    async def _async_update_data(self) -> dict[str, MowerAttributes]:
        """Subscribe for websocket and poll data from the API."""
        if not self.ws_connected:
            await self.api.connect()
            self.api.register_data_callback(self.callback)
            self.ws_connected = True
        try:
            return await self.api.get_status()
        except ApiException as err:
            raise UpdateFailed(err) from err

    @callback
    def callback(self, ws_data: dict[str, MowerAttributes]) -> None:
        """Process websocket callbacks and write them to the DataUpdateCoordinator."""
        self.async_set_updated_data(ws_data)

    async def client_listen(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        automower_client: AutomowerSession,
        reconnect_time: int = 2,
    ) -> None:
        """Listen with the client."""
        try:
            await automower_client.auth.websocket_connect()
            reconnect_time = 2
            await automower_client.start_listening()
        except HusqvarnaWSServerHandshakeError as err:
            _LOGGER.debug(
                "Failed to connect to websocket. Trying to reconnect: %s", err
            )

        if not hass.is_stopping:
            await asyncio.sleep(reconnect_time)
            reconnect_time = min(reconnect_time * 2, MAX_WS_RECONNECT_TIME)
            await self.client_listen(
                hass=hass,
                entry=entry,
                automower_client=automower_client,
                reconnect_time=reconnect_time,
            )
