"""Paperless-ngx Status coordinator."""

from datetime import timedelta

from pypaperless import Paperless
from pypaperless.exceptions import BadJsonResponseError
from pypaperless.models.status import Status

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PaperlessConfigEntry
from .const import LOGGER


class PaperlessStatusCoordinator(DataUpdateCoordinator[Status]):
    """Coordinator to manage Paperless-ngx status updates."""

    def __init__(
        self, hass: HomeAssistant, entry: PaperlessConfigEntry, api: Paperless
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Paperless-ngx Status",
            config_entry=entry,
            update_interval=timedelta(seconds=10),
            always_update=True,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self.api.status()
        except BadJsonResponseError as err:
            response = err.args[0]
            status_code = response.status
            if status_code == 401:
                LOGGER.debug(
                    "Paperless-ngx API returned 401 Not authorized. "
                    "Check if the access token is valid",
                )
                return None
            if status_code == 403:
                LOGGER.debug(
                    "Paperless-ngx API returned 403 Forbidden. "
                    "Check if the access token is valid and the user has the required permissions",
                )
                return None
        except Exception:  # noqa: BLE001
            if self._attr_available:
                LOGGER.debug(
                    "An error occurred while updating the Paperless-ngx sensor",
                    exc_info=True,
                )
                return None
