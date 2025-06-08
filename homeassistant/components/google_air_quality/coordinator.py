"""Coordinator for fetching data from Google Air Quality API."""

import datetime
import logging
from typing import Final

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import GoogleAirQualityApiError
from google_air_quality_api.model import AirQualityData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = datetime.timedelta(hours=1)

type GoogleAirQualityConfigEntry = ConfigEntry[GoogleAirQualityUpdateCoordinator]


class GoogleAirQualityUpdateCoordinator(
    DataUpdateCoordinator[dict[str, AirQualityData]]
):
    """Coordinator for fetching Google AirQuality data."""

    config_entry: GoogleAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleAirQualityConfigEntry,
        client: GoogleAirQualityApi,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.config_entry = config_entry

    async def _async_update_data(self) -> dict[str, AirQualityData]:
        """Fetch air quality data from API."""

        subentry_ids = list(self.config_entry.subentries)
        coordinates: list[tuple[float, float]] = [
            (
                self.config_entry.subentries[sid].data[CONF_LATITUDE],
                self.config_entry.subentries[sid].data[CONF_LONGITUDE],
            )
            for sid in subentry_ids
        ]

        try:
            results = await self.client.async_air_quality_multiple(coordinates)
        except GoogleAirQualityApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
                translation_placeholders={"err": str(err)},
            ) from err

        return dict(zip(subentry_ids, results, strict=False))
