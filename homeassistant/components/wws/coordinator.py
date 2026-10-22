"""Coordinator for the WWS integration."""

from collections.abc import Sequence
from datetime import timedelta
import logging
from typing import Any, override

from pyenergiedock import DynamiT, EdAuthError, EdError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=15)


class WwsCoordinator(
    TimestampDataUpdateCoordinator[dict[str, Sequence[dict[str, Any]]]]
):
    """Coordinator to fetch WWS energy prices and measurements."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: DynamiT
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="WWS energy prices",
            update_interval=UPDATE_INTERVAL,
        )
        self._api = api

    @override
    async def _async_update_data(self) -> dict[str, Sequence[dict[str, Any]]]:
        """Fetch the latest prices and measurements from the API."""
        try:
            prices = await self._api.async_get_latest_prices()
        except EdError as err:
            raise UpdateFailed from err

        try:
            measurements = await self._api.async_get_latest_measurements()
        except EdAuthError as err:
            raise UpdateFailed from err
        except EdError:
            LOGGER.debug("Could not fetch WWS measurements", exc_info=True)
            measurements = []

        return {"prices": prices, "measurements": measurements}
