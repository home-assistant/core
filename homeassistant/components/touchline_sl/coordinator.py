"""Define an object to manage fetching Touchline SL data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pytouchlinesl import Module, Zone
from pytouchlinesl.client import RothAPIError
from pytouchlinesl.client.models import GlobalScheduleModel

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class TouchlineSLModuleData:
    """Provide type safe way of accessing module data from the coordinator."""

    module: Module
    zones: dict[int, Zone]
    schedules: dict[str, GlobalScheduleModel]


class TouchlineSLModuleCoordinator(DataUpdateCoordinator[TouchlineSLModuleData]):
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

    async def _async_update_data(self) -> TouchlineSLModuleData:
        """Fetch data from the upstream API and pre-process into the right format."""
        try:
            zones = await self.module.zones()
            schedules = await self.module.schedules()
        except RothAPIError as error:
            if error.status == 401:
                # Trigger a reauthentication if the data update fails due to
                # bad authentication.
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed(error) from error

        return TouchlineSLModuleData(
            module=self.module,
            zones={z.id: z for z in zones},
            schedules={s.name: s for s in schedules},
        )
