"""Coordinator for Google Health."""

from datetime import timedelta
import logging
from typing import override

from google_health_api import GoogleHealthApi
from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
    HealthAuthException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POLLING_INTERVAL = timedelta(minutes=15)


class GoogleHealthCoordinator(DataUpdateCoordinator[int]):
    """Coordinator to fetch steps data from Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=POLLING_INTERVAL,
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> int:
        """Fetch steps count rollup for today."""
        try:
            rollup = await self.api.steps.today()
        except (HealthAuthException, HealthApiForbiddenException) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except GoogleHealthApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if rollup is None:
            return 0
        return rollup.data.count_sum
