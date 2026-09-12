"""DataUpdateCoordinator for INDI Allsky integration."""

import logging
from typing import override

from aioindiallsky import IndiAllSkyClient, IndiAllSkyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

type IndiAllSkyConfigEntry = ConfigEntry[IndiAllSkyDataUpdateCoordinator]


class IndiAllSkyDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching INDI Allsky data from the API."""

    def __init__(self, hass: HomeAssistant, entry: IndiAllSkyConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = IndiAllSkyClient(
            host=entry.data[CONF_HOST],
            port=int(entry.data[CONF_PORT]),
            ssl=get_ssl_context(
                entry.data[CONF_SSL],
                entry.data[CONF_VERIFY_SSL],
            ),
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )

    @override
    async def _async_update_data(self) -> None:
        """Fetch INDI Allsky metadata and verify connection."""
        try:
            await self.client.fetch_image("latestimage")
        except IndiAllSkyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
