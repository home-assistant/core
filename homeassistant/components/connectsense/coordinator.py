from __future__ import annotations

import logging
from typing import Any

from rebooterpro_async import RebooterError, RebooterProClient

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import ConnectSenseConfigEntry

_LOGGER = logging.getLogger(__name__)


class ConnectSenseCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator to manage communication with a Rebooter Pro device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConnectSenseConfigEntry,
        client: RebooterProClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.title or entry.unique_id or entry.entry_id}",
            update_interval=None,  # Manual refresh only; we just need initial health check today.
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch basic device info as a lightweight health check."""
        try:
            return await self.client.get_info()
        except RebooterError as exc:
            raise UpdateFailed(
                f"Failed to talk to Rebooter Pro at {self.entry.data.get(CONF_HOST)}"
            ) from exc
