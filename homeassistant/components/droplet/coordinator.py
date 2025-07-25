"""Droplet device data update coordinator object."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from dateutil.relativedelta import MO, relativedelta
from pydroplet.droplet import Droplet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOST,
    CONF_PAIRING_CODE,
    CONF_PORT,
    DOMAIN,
    RECONNECT_DELAY,
    AccumulatedVolume,
)

ML_L_CONVERSION = 1000

_LOGGER = logging.getLogger(__name__)


type DropletConfigEntry = ConfigEntry[DropletDataCoordinator]


class DropletDataCoordinator(DataUpdateCoordinator[None]):
    """Droplet device object."""

    config_entry: DropletConfigEntry
    unsub: Callable | None
    daily_volume_next_reset = dt_util.start_of_local_day() + timedelta(days=1)

    def __init__(self, hass: HomeAssistant, entry: DropletConfigEntry) -> None:
        """Initialize the device."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}-{entry.unique_id}"
        )
        self.droplet = Droplet(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            token=entry.data[CONF_PAIRING_CODE],
            session=async_get_clientsession(self.hass),
            logger=_LOGGER,
        )
        for interval in AccumulatedVolume:
            self.droplet.add_accumulator(interval, self._make_reset_time(interval))

    def _make_reset_time(self, interval: AccumulatedVolume) -> datetime:
        """Calculate reset time for an daily, weekly, or monthly interval."""
        today = dt_util.start_of_local_day()
        match interval:
            case AccumulatedVolume.DAILY:
                return today + timedelta(days=1)
            case AccumulatedVolume.WEEKLY:
                return today + relativedelta(weeks=1, weekday=MO)
            case AccumulatedVolume.MONTHLY:
                # Singular 'day' replaces day value
                # while plural 'months' adds
                return today + relativedelta(months=1, day=1)

    async def setup(self) -> bool:
        """Set up droplet client."""

        async def listen() -> None:
            """Listen for state changes via WebSocket."""
            while True:
                connected = await self.droplet.connect()
                if connected:
                    # This will only return if there was a broken connection
                    await self.droplet.listen(callback=self.async_set_updated_data)

                self.async_set_updated_data(None)
                await asyncio.sleep(RECONNECT_DELAY)

        async def disconnect(_: Event) -> None:
            """Close WebSocket connection."""
            self.unsub = None
            await self.droplet.disconnect()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, disconnect
        )
        self.config_entry.async_create_background_task(
            self.hass, listen(), "droplet-listen"
        )
        return True

    def get_daily_volume(self) -> float:
        """Retrieve daily volume usage."""
        return self._get_cumulative_volume(AccumulatedVolume.DAILY)

    def get_weekly_volume(self) -> float:
        """Retrieve weekly volume usage."""
        return self._get_cumulative_volume(AccumulatedVolume.WEEKLY)

    def get_monthly_volume(self) -> float:
        """Retrieve monthly volume usage."""
        return self._get_cumulative_volume(AccumulatedVolume.MONTHLY)

    def _get_cumulative_volume(self, interval: AccumulatedVolume) -> float:
        if self.droplet.accumulator_expired(dt_util.now(), interval):
            self.droplet.reset_accumulator(interval, self._make_reset_time(interval))
        return self.droplet.get_accumulated_volume(interval) * ML_L_CONVERSION

    def get_volume_delta(self) -> float:
        """Get volume since the last point."""
        return self.droplet.get_volume_delta() * ML_L_CONVERSION

    def get_flow_rate(self) -> float:
        """Retrieve Droplet's latest flow rate."""
        return self.droplet.get_flow_rate()

    def get_availability(self) -> bool:
        """Retrieve Droplet's availability status."""
        return self.droplet.get_availability()

    def get_server_status(self) -> str:
        """Retrieve Droplet's connection status to Hydrific servers."""
        return self.droplet.get_server_status()

    def get_signal_quality(self) -> str:
        """Retrieve Droplet's signal quality."""
        return self.droplet.get_signal_quality()
