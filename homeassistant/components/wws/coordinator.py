"""Coordinator for the WWS integration."""

from collections.abc import Sequence
from datetime import datetime, timedelta
import logging
from typing import Any, override

from pyenergiedock import DynamiT, EdAuthError, EdError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=15)

type WwsConfigEntry = ConfigEntry[WwsCoordinator]


class WwsCoordinator(
    TimestampDataUpdateCoordinator[dict[str, Sequence[dict[str, Any]]]]
):
    """Coordinator to fetch WWS energy prices and measurements."""

    def __init__(
        self, hass: HomeAssistant, config_entry: WwsConfigEntry, api: DynamiT
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
        config_entry.async_on_unload(
            async_track_time_change(
                hass,
                self._async_notify_listeners,
                minute=[0, 15, 30, 45],
                second=0,
            )
        )

    @callback
    def _async_notify_listeners(self, now: datetime) -> None:
        """Refresh time-dependent entity states at quarter-hour boundaries."""
        if self.data is not None:
            self.async_update_listeners()

    @override
    async def _async_update_data(self) -> dict[str, Sequence[dict[str, Any]]]:
        """Fetch the latest prices and measurements from the API."""
        try:
            prices = await self._api.async_get_latest_prices()
        except EdAuthError as err:
            raise ConfigEntryAuthFailed from err
        except EdError as err:
            raise UpdateFailed(str(err)) from err

        try:
            measurements = await self._api.async_get_latest_measurements()
        except EdAuthError as err:
            raise ConfigEntryAuthFailed from err
        except EdError:
            LOGGER.debug("Could not fetch WWS measurements", exc_info=True)
            measurements = []

        return {"prices": prices, "measurements": measurements}
