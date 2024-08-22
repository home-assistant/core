"""JustNimbus coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import justnimbus

from homeassistant.const import CONF_CLIENT_ID
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ZIP_CODE, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class JustNimbusCoordinator(DataUpdateCoordinator[justnimbus.JustNimbusModel]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self._client = justnimbus.JustNimbusClient(
            client_id=entry.data[CONF_CLIENT_ID], zip_code=entry.data[CONF_ZIP_CODE]
        )

    async def _async_update_data(self) -> justnimbus.JustNimbusModel:
        """Fetch the latest data from the source."""
        return await self.hass.async_add_executor_job(self._client.get_data)
