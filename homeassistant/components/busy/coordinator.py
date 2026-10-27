"""Polling state for BUSY Bar."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarAPIError, BusyBarError
from busylib.transports import AiohttpTransport
from busylib.types import Status, StatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
type BusyConfigEntry = ConfigEntry[BusyCoordinator]


@dataclass
class BusyData:
    """Status and Wi-Fi responses from one poll."""

    status: Status
    wifi: StatusResponse


class BusyCoordinator(DataUpdateCoordinator[BusyData]):
    """Poll BUSY Bar status."""

    config_entry: BusyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BusyConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self.client = AsyncBusyBar(
            entry.data[CONF_HOST],
            token=entry.data[CONF_TOKEN],
            transport=AiohttpTransport(async_get_clientsession(hass)),
            timeout=10,
        )

    @override
    async def _async_update_data(self) -> BusyData:
        """Read status and Wi-Fi information."""
        try:
            return BusyData(await self.client.status(), await self.client.wifi_status())
        except BusyBarError as err:
            if isinstance(err, BusyBarAPIError) and err.status_code in (401, 403):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            raise UpdateFailed("Cannot read BUSY Bar") from err
