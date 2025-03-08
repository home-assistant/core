"""Coordinator for the Airios integration."""

from __future__ import annotations

import datetime
import logging

from pyairios import Airios
from pyairios.data_model import AiriosData
from pyairios.exceptions import AiriosException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


class AiriosDataUpdateCoordinator(DataUpdateCoordinator[AiriosData]):
    """The Airios data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Airios,
        update_interval: int,
    ) -> None:
        """Initialize the Airios data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DEFAULT_NAME} DataUpdateCoordinator",
            update_interval=datetime.timedelta(seconds=update_interval),
        )
        self.api = api

    async def _async_update_data(self) -> AiriosData:
        """Fetch state from API."""
        _LOGGER.debug("Updating data state cache")
        try:
            return await self.api.fetch()
        except AiriosException as err:
            raise UpdateFailed("Error during state cache update") from err
