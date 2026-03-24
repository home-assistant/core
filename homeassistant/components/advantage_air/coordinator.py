"""Coordinator for the Advantage Air integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from advantage_air import ApiError, advantage_air

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

ADVANTAGE_AIR_SYNC_INTERVAL = 15
REQUEST_REFRESH_DELAY = 0.5

_LOGGER = logging.getLogger(__name__)

type AdvantageAirDataConfigEntry = ConfigEntry[AdvantageAirCoordinator]


class AdvantageAirCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Advantage Air coordinator."""

    config_entry: AdvantageAirDataConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AdvantageAirDataConfigEntry,
        api: advantage_air,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Advantage Air",
            update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            return await self.api.async_get()
        except ApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
