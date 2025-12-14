"""Coordinator for the Airobot integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyairobotrest import AirobotClient
from pyairobotrest.exceptions import AirobotAuthError, AirobotConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import AirobotData

_LOGGER = logging.getLogger(__name__)

# Update interval - thermostat measures air every 30 seconds
UPDATE_INTERVAL = timedelta(seconds=30)

type AirobotConfigEntry = ConfigEntry[AirobotDataUpdateCoordinator]


class AirobotDataUpdateCoordinator(DataUpdateCoordinator[AirobotData]):
    """Class to manage fetching Airobot data."""

    config_entry: AirobotConfigEntry

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

    async def _async_update_data(self) -> AirobotData:
        """Fetch data from API endpoint."""
        try:
            status = await self.client.get_statuses()
            settings = await self.client.get_settings()
        except AirobotAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except AirobotConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err

        return AirobotData(status=status, settings=settings)
