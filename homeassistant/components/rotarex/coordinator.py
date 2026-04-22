"""DataUpdateCoordinator for the Rotarex integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

import aiohttp
from rotarex_dimes_srg_api import InvalidAuth, RotarexApi, RotarexSyncData, RotarexTank

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from . import RotarexConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


def _parse_synch_date(synch_date: str) -> datetime | None:
    """Parse a synch_date string, replacing timezone with HA local timezone.

    The API returns local time incorrectly tagged as UTC (+00:00).
    We strip any timezone info and reattach the HA configured local timezone.
    """
    parsed = dt_util.parse_datetime(synch_date)
    if parsed is None:
        return None
    return parsed.replace(tzinfo=dt_util.get_default_time_zone())


def _latest_sync(tank: RotarexTank) -> tuple[RotarexSyncData | None, datetime | None]:
    """Return the most recent synchronization entry for the tank and its parsed datetime."""
    latest_sync: RotarexSyncData | None = None
    latest_parsed: datetime | None = None
    for sync in tank.synch_datas:
        parsed = _parse_synch_date(sync.synch_date)
        if parsed is None:
            continue
        if latest_parsed is None or parsed > latest_parsed:
            latest_sync = sync
            latest_parsed = parsed
    return latest_sync, latest_parsed


@dataclass(slots=True)
class RotarexTankData:
    """Per-tank data computed once per coordinator update."""

    tank: RotarexTank
    latest_sync: RotarexSyncData | None
    latest_sync_dt: datetime | None


class RotarexDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RotarexTankData]]
):
    """Class to manage fetching Rotarex data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RotarexConfigEntry,
    ) -> None:
        """Initialize the data update coordinator."""
        session = async_get_clientsession(hass)
        self.api = RotarexApi(session)
        self.api.set_credentials(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator with initial authentication check."""
        assert self.config_entry is not None
        try:
            await self.api.login(
                self.config_entry.data[CONF_EMAIL],
                self.config_entry.data[CONF_PASSWORD],
            )
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def _async_update_data(self) -> dict[str, RotarexTankData]:
        """Fetch data from API endpoint."""
        try:
            tanks = await self.api.fetch_tanks()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        result: dict[str, RotarexTankData] = {}
        for tank in tanks:
            sync, sync_dt = _latest_sync(tank)
            result[tank.guid] = RotarexTankData(
                tank=tank, latest_sync=sync, latest_sync_dt=sync_dt
            )
        return result
