"""Data update coordinator for TSUN micro-inverters."""

from datetime import timedelta
import logging
from typing import override

from tsun_local_api import Telemetry, TsunClient, TsunError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TsunDataUpdateCoordinator(DataUpdateCoordinator[Telemetry]):
    """Coordinate polling for one TSUN micro-inverter."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: TsunClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> Telemetry:
        """Fetch telemetry from the micro-inverter."""
        try:
            telemetry = await self.client.async_read()
        except TsunError as err:
            raise UpdateFailed("Unable to update TSUN telemetry") from err
        return telemetry
