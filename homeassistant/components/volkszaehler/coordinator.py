"""Coordinator for Volkszaehler."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import VolkszaehlerApiConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VolkszaehlerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch data from Volkszaehler API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Volkszaehler,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Volkszaehler API."""
        try:
            await self.api.get_data()
        except VolkszaehlerApiConnectionError as err:
            _LOGGER.error("Fehler beim Abrufen der Daten von Volkszaehler: %s", err)
            raise UpdateFailed(f"Fehler beim Abrufen der Daten: {err}") from err
        else:
            return self.api or {}
