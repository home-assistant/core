"""Data UpdateCoordinator for the Husqvarna Automower integration."""
from dataclasses import fields
from datetime import timedelta
import logging

import aioautomower

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[aioautomower.MowerList]):
    """Class to manage fetching Husqvarna data."""

    def __init__(
        self,
        hass: HomeAssistant,
        implementation,
        session: OAuth2Session,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=300),
        )
        self.mowersession = aioautomower.AutomowerSession(
            implementation.client_id,
            session.token,
            low_energy=False,
            handle_token=False,
            handle_rest=False,
        )
        self.ws_connected: bool = False

    async def _async_update_data(self) -> None:
        """Subscribe for websocket and poll data from the API."""
        if not self.ws_connected:
            await self.mowersession.connect()
            self.mowersession.register_data_callback(
                self.callback, schedule_immediately=True
            )
            self.ws_connected = True
        return await self.mowersession.get_status()

    @callback
    def callback(self, ws_data: aioautomower.MowerData):
        """Process websocket callbacks and write them to the DataUpdateCoordinator."""
        if self.data and ws_data:
            for mower in self.data.data:
                if mower.id == ws_data.id:
                    for field in fields(ws_data.attributes):
                        field_value = getattr(ws_data.attributes, field.name)
                        if field_value:
                            setattr(mower.attributes, field.name, field_value)
        self.async_set_updated_data(self.data)
