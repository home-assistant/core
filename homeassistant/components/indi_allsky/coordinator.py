"""DataUpdateCoordinator for INDI Allsky integration."""

from dataclasses import dataclass
import logging
from typing import override

from aioindiallsky import ExposureData, IndiAllSkyClient, IndiAllSkyError, MediaData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

type IndiAllSkyConfigEntry = ConfigEntry[IndiAllSkyDataUpdateCoordinator]


@dataclass
class IndiAllSkyData:
    """Data model for INDI Allsky coordinator data."""

    exposure: ExposureData | None = None
    latest_keogram: MediaData | None = None
    latest_startrail: MediaData | None = None


class IndiAllSkyDataUpdateCoordinator(DataUpdateCoordinator[IndiAllSkyData]):
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
        self.latest_keogram: MediaData | None = None
        self.latest_startrail: MediaData | None = None

        unsub_exp = self.client.register_callback(
            "exposure_complete", self._handle_exposure_complete
        )
        unsub_keogram = self.client.register_callback(
            "keogram_complete", self._handle_keogram_complete
        )
        unsub_startrail = self.client.register_callback(
            "startrail_complete", self._handle_startrail_complete
        )
        entry.async_on_unload(unsub_exp)
        entry.async_on_unload(unsub_keogram)
        entry.async_on_unload(unsub_startrail)
        entry.async_on_unload(self.client.disconnect)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )

    def _handle_exposure_complete(self, exposure: ExposureData) -> None:
        """Handle new exposure_complete event from WebSocket stream."""
        self.latest_exposure = exposure
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=exposure,
                latest_keogram=self.latest_keogram,
                latest_startrail=self.latest_startrail,
            )
        )

    def _handle_keogram_complete(self, media: MediaData) -> None:
        """Handle new keogram_complete event from WebSocket stream."""
        self.latest_keogram = media
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=self.latest_exposure,
                latest_keogram=media,
                latest_startrail=self.latest_startrail,
            )
        )

    def _handle_startrail_complete(self, media: MediaData) -> None:
        """Handle new startrail_complete event from WebSocket stream."""
        self.latest_startrail = media
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=self.latest_exposure,
                latest_keogram=self.latest_keogram,
                latest_startrail=media,
            )
        )

    @override
    async def _async_update_data(self) -> IndiAllSkyData:
        """Fetch INDI Allsky metadata and verify connection."""
        try:
            await self.client.fetch_image("latestimage")
            if not self.client.is_connected:
                await self.client.connect()
        except IndiAllSkyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        return IndiAllSkyData(
            exposure=self.latest_exposure,
            latest_keogram=self.latest_keogram,
            latest_startrail=self.latest_startrail,
        )
