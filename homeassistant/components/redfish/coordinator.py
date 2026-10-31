"""Data coordinator for Redfish."""

import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RedfishApi, RedfishAuthError, RedfishError
from .const import CONF_BASE_URL, DOMAIN, UPDATE_INTERVAL
from .models import RedfishData

_LOGGER = logging.getLogger(__name__)

type RedfishConfigEntry = ConfigEntry[RedfishDataUpdateCoordinator]


class RedfishDataUpdateCoordinator(DataUpdateCoordinator[RedfishData]):
    """Coordinate Redfish polling."""

    config_entry: RedfishConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RedfishConfigEntry) -> None:
        """Initialize coordinator."""
        self.client = RedfishApi(
            async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
            entry.data[CONF_BASE_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> RedfishData:
        """Fetch Redfish data."""
        try:
            data = await self.client.async_discover()
        except RedfishAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except RedfishError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
        if not data.systems:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_systems")
        return data
