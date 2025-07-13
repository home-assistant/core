"""PoolDose API Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from pooldose.client import PooldoseClient
from pooldose.request_handler import RequestStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import PooldoseConfigEntry

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PooldoseCoordinator(DataUpdateCoordinator[tuple[RequestStatus, dict[str, Any]]]):
    """Coordinator for PoolDose API."""

    config_entry: PooldoseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: PooldoseClient,
        update_interval: timedelta,
        config_entry: PooldoseConfigEntry,
    ) -> None:
        """Initialize the PoolDose coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="pooldose",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> tuple[RequestStatus, dict[str, Any]]:
        """Fetch data from the PoolDose API."""
        try:
            return await self.client.instant_values()
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    @property
    def available(self) -> bool:
        """Return True if coordinator is available."""
        return self.last_update_success
