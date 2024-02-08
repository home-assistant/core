"""The microBees Coordinator."""

import asyncio
from datetime import timedelta
import logging

import aiohttp
from microBeesPy.microbees import Actuator, Bee

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


class MicroBeesUpdateCoordinator(DataUpdateCoordinator):
    """MicroBees coordinator."""

    def __init__(self, hass: HomeAssistant, microBees) -> None:
        """Initialize microBees coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="microBees Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self.microBees = microBees

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                return await self.microBees.getBees()
        except aiohttp.ClientResponseError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class MicroBeesEntity(CoordinatorEntity[MicroBeesUpdateCoordinator]):
    """Base class for microBees entities."""

    def __init__(
        self, coordinator: MicroBeesUpdateCoordinator, act: Actuator, bee: Bee
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator)
        self._attr_available = False
        self.bee_id = bee.id
        self.act_id = act.id

    @property
    def updated_bee(self) -> Bee:
        """Return the updated bee."""
        return next(filter(lambda x: x.id == self.bee_id, self.coordinator.data))

    @property
    def updated_act(self) -> Actuator:
        """Return the updated act."""
        if self.act is None:
            return None
        return next(filter(lambda x: x.id == self.act_id, self.updated_bee.actuators))
