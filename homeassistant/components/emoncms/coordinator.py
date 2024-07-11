"""DataUpdateCoordinator for the emoncms integration."""

from datetime import timedelta
from typing import Any

from pyemoncms import EmoncmsClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


class EmoncmsCoordinator(DataUpdateCoordinator[list[dict[str, Any]] | None]):
    """Emoncms Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        emoncms_client: EmoncmsClient,
    ) -> None:
        """Initialize the emoncms data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="emoncms_coordinator",
            update_method=emoncms_client.async_list_feeds,
            update_interval=timedelta(seconds=60),
        )
