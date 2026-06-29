"""Coordinator for Google Health."""

from datetime import timedelta
import logging
from typing import Any, override

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


class GoogleHealthCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch steps count rollup for today."""
        if self.config_entry is None:
            return {}
        scopes = self.config_entry.data.get("token", {}).get("scope", "").split()
        data: dict[str, Any] = {}

        required_scopes = self.api.steps.required_read_scopes
        if all(scope in scopes for scope in required_scopes):
            try:
                rollup = await self.api.steps.today(self.hass.config.time_zone)
                data["steps"] = rollup.data.count_sum if rollup else 0
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

        return data
