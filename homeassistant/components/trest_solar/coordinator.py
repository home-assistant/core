from __future__ import annotations  # noqa: D100

from datetime import timedelta
import logging

from trest_solar import CloudSolarTrestService, SolarHistory

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

REFRESH_INTERVAL = 30

_LOGGER = logging.getLogger(__name__)


class TrestDataCoordinator(DataUpdateCoordinator[SolarHistory]):
    """Trest coordinator."""

    def __init__(self, hass: HomeAssistant, logger: logging.Logger) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger,
            name="Trest Solar Controller",
            update_interval=timedelta(seconds=REFRESH_INTERVAL),
        )

        if self.config_entry is not None:
            self.trest_solar_service = CloudSolarTrestService(
                self.config_entry.data["username"],
                self.config_entry.data["password"],
            )
        else:
            raise MissingConfigEntryException("Missing config entry")

    async def _async_update_data(self) -> SolarHistory:
        """Fetch data from Trest Cloud."""

        _LOGGER.info("Requesting Solar History data from Cloud Trest")
        response = await self.trest_solar_service.get_latest_solar_history_async()

        solar_history = SolarHistory(response)

        return solar_history


class MissingConfigEntryException(Exception):
    """Missing the config entry."""
