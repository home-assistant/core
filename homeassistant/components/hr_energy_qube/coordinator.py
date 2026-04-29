"""DataUpdateCoordinator for Qube Heat Pump."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from python_qube_heatpump import QubeClient
from python_qube_heatpump.models import QubeState

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class QubeCoordinator(DataUpdateCoordinator[QubeState]):
    """Qube Heat Pump data coordinator."""

    def __init__(
        self, hass: HomeAssistant, client: QubeClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )

    async def _async_update_data(self) -> QubeState:
        """Fetch data from the device."""
        try:
            data = await self.client.get_all_data()
        except (ConnectionError, TimeoutError, OSError) as exc:
            raise UpdateFailed(
                f"Error communicating with Qube heat pump: {exc}"
            ) from exc

        if data is None:
            raise UpdateFailed("No data received from Qube heat pump")

        return data
