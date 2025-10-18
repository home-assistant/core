"""Data update coordinator for the Sony Projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ProjectorClient, ProjectorClientError, ProjectorState
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

if TYPE_CHECKING:
    from . import SonyProjectorConfigEntry

_LOGGER = logging.getLogger(__name__)


class SonyProjectorCoordinator(DataUpdateCoordinator[ProjectorState]):
    """Coordinator to manage projector updates."""

    config_entry: SonyProjectorConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: ProjectorClient,
        entry: SonyProjectorConfigEntry,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
            config_entry=entry,
        )
        self.client = client
        self.last_error: str | None = None

    async def _async_update_data(self) -> ProjectorState:
        """Fetch data from the projector."""

        try:
            state = await self.client.async_get_state()
        except ProjectorClientError as err:
            self.last_error = str(err)
            raise UpdateFailed(str(err)) from err

        self.last_error = None
        return state
