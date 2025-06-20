"""JustNimbus coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

import justnimbus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ZIP_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

type JustNimbusConfigEntry = ConfigEntry[JustNimbusCoordinator]


class JustNimbusCoordinator(DataUpdateCoordinator[justnimbus.JustNimbusModel]):
    """Data update coordinator."""

    config_entry: JustNimbusConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: JustNimbusConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self._client = justnimbus.JustNimbusClient(
            client_id=config_entry.data[CONF_CLIENT_ID],
            zip_code=config_entry.data[CONF_ZIP_CODE],
        )

    async def _async_update_data(self) -> justnimbus.JustNimbusModel:
        """Fetch the latest data from the source."""
        return await self.hass.async_add_executor_job(self._client.get_data)
