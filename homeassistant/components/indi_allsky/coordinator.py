"""DataUpdateCoordinator for INDI Allsky integration."""

from datetime import timedelta
import logging
from typing import Any, override

from aioindiallsky import ExposureData, IndiAllSkyClient, IndiAllSkyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

type IndiAllSkyConfigEntry = ConfigEntry[IndiAllSkyDataUpdateCoordinator]


class IndiAllSkyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self.latest_exposure: ExposureData | None = None

        self.client.register_callback(
            "exposure_complete", self._handle_exposure_complete
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    def _handle_exposure_complete(self, exposure: ExposureData) -> None:
        """Handle new exposure_complete event from WebSocket stream."""
        self.latest_exposure = exposure
        current_data = self.data if self.data is not None else {"image_bytes": None}
        self.async_set_updated_data({**current_data, "exposure": exposure})

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch image bytes from INDI Allsky camera."""
        try:
            image_bytes = await self.client.fetch_image("latestimage")
        except IndiAllSkyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        return {
            "image_bytes": image_bytes,
            "exposure": self.latest_exposure,
        }
