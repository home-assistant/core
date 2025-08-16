"""Data update coordinator for Vitrea integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from vitreaclient.client import VitreaClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VitreaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Vitrea data polling."""

    def __init__(
        self, hass: HomeAssistant, client: VitreaClient, config_entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Vitrea client."""
        try:
            # Since VitreaClient is event-based, we can return current state
            # or implement a status polling method if available
            return {"status": "connected", "last_update": self.last_update_success}
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with Vitrea device: {err}"
            ) from err
