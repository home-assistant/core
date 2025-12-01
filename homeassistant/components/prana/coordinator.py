"""Coordinator for Prana integration.

Responsible for polling the device REST endpoints and normalizing data for entities.
"""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import PranaConfigEntry


from prana_local_api_client.exceptions import (
    PranaApiCommunicationError,
    PranaApiUpdateFailed,
)
from prana_local_api_client.models.prana_state import PranaState
from prana_local_api_client.prana_api_client import PranaLocalApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PranaCoordinator(DataUpdateCoordinator[PranaState]):
    """Universal coordinator for Prana (fan, switch, sensor, light data)."""

    def __init__(self, hass: HomeAssistant, entry: "PranaConfigEntry") -> None:
        """Initialize the Prana data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=10),
            update_method=self._async_update_data,
            config_entry=entry,
        )
        self.entry = entry
        self.max_speed: int | None = None

        host = self.entry.data[CONF_HOST]
        self.api_client = PranaLocalApiClient(host=host, port=80)

    async def _async_update_data(self) -> PranaState:
        """Fetch and normalize device state for all platforms."""
        try:
            state = await self.api_client.get_state()
        except PranaApiUpdateFailed as err:
            raise UpdateFailed(f"HTTP error communicating with device: {err}") from err
        except PranaApiCommunicationError as err:
            raise UpdateFailed(
                f"Network error communicating with device: {err}"
            ) from err
        return state
