"""Data update coordinator for TSUN micro-inverters."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from tsun_local_api import Telemetry, TsunClient, TsunError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_POLL_LOCK = "poll_lock"


def get_poll_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return one lock shared by all configured TSUN micro-inverters."""
    # This process-wide lock serializes full reads across multiple config entries.
    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_POLL_LOCK, asyncio.Lock())


class TsunDataUpdateCoordinator(DataUpdateCoordinator[Telemetry]):
    """Coordinate polling for one TSUN micro-inverter."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: TsunClient,
        *,
        poll_lock: asyncio.Lock,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self._poll_lock = poll_lock

    @override
    async def _async_update_data(self) -> Telemetry:
        """Fetch telemetry from the micro-inverter."""
        try:
            # Local loggers are small devices. Complete exchanges are serialized
            # so multiple configured inverters are never polled simultaneously.
            async with self._poll_lock:
                telemetry = await self.client.async_read()
        except TsunError as err:
            raise UpdateFailed("Unable to update TSUN telemetry") from err
        return telemetry
