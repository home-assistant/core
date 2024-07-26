"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import logging
from typing import TYPE_CHECKING, Any

import evohomeasync2 as evo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import utcnow

from .const import CONF_EXPIRES, CONF_REFRESH_TOKEN, SCAN_INTERVAL_DEFAULT
from .helpers import handle_evo_exception

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


lock = asyncio.Lock()


class EvohomeDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Evohome data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, v2_client: evo.EvohomeClient) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass, _LOGGER, name="Evohome", update_interval=SCAN_INTERVAL_DEFAULT
        )
        self.client = v2_client
        self.temps: dict[str, float | None] = {}

    async def _async_update_data(self) -> None:
        async with lock:
            if self.config_entry.data[CONF_EXPIRES] < utcnow():
                await self.client.login()
                await self._save_tokens()
        try:
            for location in self.client.locations:
                await location.refresh_status()
        except evo.AuthenticationFailed as err:
            raise ConfigEntryError("Authentication failed") from err
        except evo.RequestFailed as err:
            raise UpdateFailed(err) from err

    async def call_client_api(
        self,
        client_api: Awaitable[dict[str, Any] | None],
        update_state: bool = True,
    ) -> dict[str, Any] | None:
        """Call a client API and update the broker state if required."""

        try:
            result = await client_api
        except evo.RequestFailed as err:
            handle_evo_exception(err)
            return None

        if update_state:
            await self.async_request_refresh()

        return result

    async def _save_tokens(self) -> None:
        self.hass.config_entries.async_update_entry(
            data={
                **self.config_entry.data,
                CONF_REFRESH_TOKEN: self.client.refresh_token,
                CONF_ACCESS_TOKEN: self.client.access_token,
                CONF_EXPIRES: self.client.access_token_expires,
            }
        )
