"""Coordinator for the Airobot integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyairobotrest import AirobotClient
from pyairobotrest.exceptions import AirobotAuthError, AirobotConnectionError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import AirobotConfigEntry

_LOGGER = logging.getLogger(__name__)


class AirobotDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Airobot data."""

    config_entry: AirobotConfigEntry
    _unavailable_logged: bool = False

    def __init__(self, hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        session = async_get_clientsession(hass)

        self.client = AirobotClient(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            status = await self.client.get_statuses()
            settings = await self.client.get_settings()
        except AirobotAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except AirobotConnectionError as err:
            if not self._unavailable_logged:
                _LOGGER.info("Device is unavailable: %s", err)
                self._unavailable_logged = True
            raise UpdateFailed(f"Failed to communicate with device: {err}") from err
        else:
            if self._unavailable_logged:
                _LOGGER.info("Device is back online")
                self._unavailable_logged = False
            return {
                "status": status,
                "settings": settings,
            }
