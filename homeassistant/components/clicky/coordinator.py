"""Coordinator to handle Clicky API access."""

from datetime import timedelta
import logging
from typing import Any, override

from pyclicky import ClickyAPIError, ClickyClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, METRICS

_LOGGER = logging.getLogger(__name__)

type ClickyConfigEntry = ConfigEntry[ClickyCoordinator]


class ClickyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Handle fetching Clicky data, updating sensors and inserting statistics."""

    config_entry: ClickyConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ClickyConfigEntry, client: ClickyClient
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

        self.client = client

    @override
    async def _async_update_data(
        self,
    ) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        ret: dict[str, Any] = {}

        async with self.client as service:
            for key, val in METRICS.items():
                try:
                    response = await service.query(val)
                except ClickyAPIError as error:
                    raise UpdateFailed(
                        f"Error fetching data from API: {error}"
                    ) from error

                ret[key] = response[0]["dates"][0]["items"][0]["value"]  # int?

            return ret
