"""Coordinator for the MAWAQIT integration."""

from dataclasses import dataclass
from datetime import timedelta, tzinfo
import logging
from typing import override

from mawaqit import AsyncMawaqitClient, MawaqitError
from mawaqit.types import PrayerTimes

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RETRY_AFTER = timedelta(minutes=15)

type MawaqitConfigEntry = ConfigEntry[MawaqitCoordinator]


@dataclass
class MawaqitData:
    """Prayer times of the mosque, with its time zone."""

    prayer_times: PrayerTimes
    timezone: tzinfo


class MawaqitCoordinator(DataUpdateCoordinator[MawaqitData]):
    """Fetch the prayer times of the year of the mosque."""

    config_entry: MawaqitConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MawaqitConfigEntry,
        client: AsyncMawaqitClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> MawaqitData:
        """Fetch the prayer times."""
        try:
            prayer_times = await self.client.mosques.prayer_times(
                self.config_entry.data[CONF_UUID]
            )
        except MawaqitError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
                retry_after=RETRY_AFTER.total_seconds(),
            ) from err

        timezone = await dt_util.async_get_time_zone(prayer_times.timezone)
        if timezone is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_timezone",
                translation_placeholders={"timezone": prayer_times.timezone},
            )
        return MawaqitData(prayer_times, timezone)
