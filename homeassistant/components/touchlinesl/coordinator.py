"""Define an object to manage fetching Touchline SL data."""

from __future__ import annotations

from datetime import timedelta
import logging

from pytouchlinesl import Module, Zone
from pytouchlinesl.client import RothAPIError
from pytouchlinesl.client.models import GlobalScheduleModel

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TouchlineSLModuleCoordinator(DataUpdateCoordinator):
    """A coordinator to manage the fetching of Touchline SL data."""

    def __init__(self, hass: HomeAssistant, module: Module) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Touchline SL ({module.name})",
            update_interval=timedelta(seconds=30),
        )

        self.module = module
        self._zones: list[Zone] = []
        self._schedules: list[GlobalScheduleModel] = []

    async def _async_setup(self):
        """Set up the coordinator."""
        self._zones = await self.module.zones()
        self._schedules = await self.module.schedules()

    async def _async_update_data(
        self,
    ) -> dict[str, dict[int, Zone] | dict[str, GlobalScheduleModel]]:
        """Fetch data from the upstream API and pre-process into the right format."""
        try:
            self._zones = await self.module.zones()
            self._schedules = await self.module.schedules()

            return {
                "zones": {z.id: z for z in self._zones},
                "schedules": {s.name: s for s in self._schedules},
            }
        except RothAPIError as error:
            if error.status == 401:
                # Trigger a reauthentication if the data update fails due to
                # bad authentication.
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed(error) from error
