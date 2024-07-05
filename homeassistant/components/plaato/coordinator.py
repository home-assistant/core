"""Coordinator for Plaato devices."""

from datetime import timedelta
import logging

from pyplaato.plaato import Plaato, PlaatoDeviceType

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PlaatoCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_token: str,
        device_type: PlaatoDeviceType,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.api = Plaato(auth_token=auth_token)
        self.hass = hass
        self.device_type = device_type
        self.platforms: list[Platform] = []

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Update data via library."""
        return await self.api.get_data(
            session=aiohttp_client.async_get_clientsession(self.hass),
            device_type=self.device_type,
        )
