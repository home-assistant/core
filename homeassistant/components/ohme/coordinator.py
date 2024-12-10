"""Ohme coordinators."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from ohme import ApiException, OhmeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class OhmeApiResponse:
    """Store API response data."""

    charge_sessions: dict[str, Any]
    advanced_settings: dict[str, Any]


class OhmeCoordinator(DataUpdateCoordinator[OhmeApiResponse]):
    """Coordinator to pull all updates from the API."""

    def __init__(self, hass: HomeAssistant, client: OhmeApiClient) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self._client: OhmeApiClient = client
        self._response: OhmeApiResponse = OhmeApiResponse({}, {})
        self._alternative_iteration: bool = True

    async def _async_update_data(self) -> OhmeApiResponse:
        """Fetch data from API endpoint."""
        try:
            self._response.charge_sessions = (
                await self._client.async_get_charge_sessions()
            )

            # Fetch on every other update
            if self._alternative_iteration:
                self._response.advanced_settings = (
                    await self._client.async_get_advanced_settings()
                )

            self._alternative_iteration = not self._alternative_iteration
        except ApiException as e:
            raise UpdateFailed("Error communicating with API") from e
        else:
            return self._response
