"""Generic Omada API coordinator."""

import asyncio
from datetime import timedelta
import logging
from typing import Generic, TypeVar

from tplink_omada_client import OmadaSiteClient
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class OmadaCoordinator(DataUpdateCoordinator[dict[str, T]], Generic[T]):
    """Coordinator for synchronizing bulk Omada data."""

    def __init__(
        self,
        hass: HomeAssistant,
        omada_client: OmadaSiteClient,
        name: str,
        poll_delay: int = 300,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Omada API Data - {name}",
            update_interval=timedelta(seconds=poll_delay),
        )
        self.omada_client = omada_client

    async def _async_update_data(self) -> dict[str, T]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                return await self.poll_update()
        except OmadaClientException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def poll_update(self) -> dict[str, T]:
        """Poll the current data from the controller."""
        raise NotImplementedError("Update method not implemented")
