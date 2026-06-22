"""Coordinator for Plaato devices."""

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from pyplaato.models.device import PlaatoDevice
from pyplaato.plaato import Plaato, PlaatoDeviceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlaatoData:
    """Runtime data for the Plaato integration."""

    coordinator: PlaatoCoordinator | None
    device_name: str
    device_type: str
    device_id: str | None
    sensor_data: PlaatoDevice | None = field(default=None)


type PlaatoConfigEntry = ConfigEntry[PlaatoData]


class PlaatoCoordinator(DataUpdateCoordinator[PlaatoDevice]):
    """Class to manage fetching data from the API."""

    config_entry: PlaatoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PlaatoConfigEntry,
        auth_token: str,
        device_type: PlaatoDeviceType,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.api = Plaato(auth_token=auth_token)
        self.device_type = device_type
        self.platforms: list[Platform] = []

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> PlaatoDevice:
        """Update data via library."""
        return await self.api.get_data(
            session=aiohttp_client.async_get_clientsession(self.hass),
            device_type=self.device_type,
        )
