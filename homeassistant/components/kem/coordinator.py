"""The AccuWeather coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from aiokem import AioKem, AuthenticationError, CommunicationError, ServerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_MINUTES

RETRY_EXCEPTIONS = (
    CommunicationError,
    ServerError,
    ClientConnectorError,
)

AUTHORIZATION_EXCEPTIONS = (AuthenticationError,)

MAX_RETRIES = 3
RETRY_DELAY = [5000, 10000, 20000]

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
        self.config_entry: ConfigEntry = config_entry
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )

    async def _async_retry_auth(self) -> bool:
        """Retry authentication."""
        _LOGGER.debug("Retrying authentication %s", self.name)
        try:
            await self.kem.authenticate(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
        except AuthenticationError as error:
            _LOGGER.error("Authentication failed: %s %s", self.name, error)
            return False
        return True

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        result = {}
        for i in range(MAX_RETRIES):
            try:
                result = await self.kem.get_generator_data(self.device_id)
                break
            except RETRY_EXCEPTIONS as error:
                _LOGGER.warning("Error communicating with KEM: %s", error)
            except AUTHORIZATION_EXCEPTIONS as error:
                _LOGGER.warning("Authorization error communicating with KEM: %s", error)
                if not await self._async_retry_auth():
                    break
            await asyncio.sleep(RETRY_DELAY[i])
        if not result:
            _LOGGER.error("Failed to get data after %s retries", MAX_RETRIES)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_retry_failed",
            )
        return result
