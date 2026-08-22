"""Data coordinator for Redfish."""

import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RedfishApi, RedfishError
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
            return await self.client.async_discover()
        except RedfishError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
