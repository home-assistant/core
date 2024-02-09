"""The microBees Coordinator."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aioaseko import dataclass
import aiohttp
from microBeesPy.microbees import Actuator, Bee, MicroBees, MicroBeesException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class MicroBeesCoordinatorData:
    """Microbees data from the Coordinator."""

    bees: dict[int:Bee]
    actuators: dict[int:Actuator]


class MicroBeesUpdateCoordinator(DataUpdateCoordinator):
    """MicroBees coordinator."""

    def __init__(self, hass: HomeAssistant, microbees: MicroBees) -> None:
        """Initialize microBees coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="microBees Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self.microbees = microbees

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(10):
            try:
                bees = await self.microbees.getBees()
            except aiohttp.ClientResponseError as err:
                if err.status is HTTPStatus.UNAUTHORIZED:
                    raise ConfigEntryAuthFailed(
                        "Token not valid, trigger renewal"
                    ) from err
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            except MicroBeesException as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            bees_dict = {}
            actuators_dict = {}
            for bee in bees:
                bees_dict[bee.id] = bee
                for act in bee.actuators:
                    actuators_dict[act.id] = act
            return MicroBeesCoordinatorData(bees=bees_dict, actuators=actuators_dict)
