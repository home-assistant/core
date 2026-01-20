"""Coordinator for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pysaunum import SaunumClient, SaunumData, SaunumException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import LeilSaunaConfigEntry

_LOGGER = logging.getLogger(__name__)


class LeilSaunaCoordinator(DataUpdateCoordinator[SaunumData]):
    """Coordinator for fetching Saunum Leil Sauna data."""

    config_entry: LeilSaunaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: SaunumClient,
        config_entry: LeilSaunaConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> SaunumData:
        """Fetch data from the sauna controller."""
        try:
            return await self.client.async_get_data()
        except SaunumException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
