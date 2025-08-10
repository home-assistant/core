"""The v2c component."""

from __future__ import annotations

from datetime import timedelta
import logging

from pytrydan import Trydan, TrydanData
from pytrydan.exceptions import TrydanError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

type V2CConfigEntry = ConfigEntry[V2CUpdateCoordinator]


class V2CUpdateCoordinator(DataUpdateCoordinator[TrydanData]):
    """DataUpdateCoordinator to gather data from any v2c."""

    config_entry: V2CConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: V2CConfigEntry, evse: Trydan
    ) -> None:
        """Initialize DataUpdateCoordinator for a v2c evse."""
        self.evse = evse
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"EVSE {config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> TrydanData:
        """Fetch sensor data from api."""
        try:
            data: TrydanData = await self.evse.get_data()
        except TrydanError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        _LOGGER.debug("Received data: %s", data)
        return data
