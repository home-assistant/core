"""The AccuWeather coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from aiokem.exceptions import CommunicationError
from aiokem.main import AioKem

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

EXCEPTIONS = (CommunicationError, ClientConnectorError)

_LOGGER = logging.getLogger(__name__)


class KemUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching KEM data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        config_entry: ConfigEntry,
        kem: AioKem,
        home_data: dict[str, Any],
        device_data: dict[str, Any],
        device_id: int,
        name: str,
    ) -> None:
        """Initialize."""
        self.kem = kem
        self.device_data = device_data
        self.device_id = device_id
        self.home_data = home_data
        self.available = False
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        result = {}
        try:
            result = await self.kem.get_generator_data(self.device_id)
            self.available = True
        except EXCEPTIONS as error:
            raise UpdateFailed(error) from error
        return result
