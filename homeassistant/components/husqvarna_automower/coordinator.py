"""Data UpdateCoordinator for the Husqvarna Automower integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession
from aiohttp import ClientConnectorSSLError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
            update_interval=timedelta(minutes=5),
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

    async def shutdown(self, *_: Any) -> None:
        """Close resources."""
        await self.api.close()

    @callback
    def callback(self, ws_data: dict[str, MowerAttributes]) -> None:
        """Process websocket callbacks and write them to the DataUpdateCoordinator."""
        self.async_set_updated_data(ws_data)

    async def client_listen(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        automower_client: AutomowerSession,
        init_ready: asyncio.Event,
    ) -> None:
        """Listen with the client."""
        try:
            await automower_client.start_listening(init_ready)
        except ClientConnectorSSLError as err:
            if entry.state != ConfigEntryState.LOADED:
                raise
            _LOGGER.error("Failed to listen: %s", err)
        except Exception as err:  # pylint: disable=broad-except
            # We need to guard against unknown exceptions to not crash this task.
            _LOGGER.exception("Unexpected exception: %s", err)
            if entry.state != ConfigEntryState.LOADED:
                raise

        if not hass.is_stopping:
            _LOGGER.debug("Disconnected from server. Reloading integration")
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
