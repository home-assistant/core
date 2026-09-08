"""The ukraine_alarm component."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any, override

import aiohttp
from aiohttp import ClientSession
from uasiren.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import AIR_ALERT_LEVELS, ALERT_TYPE_AIR, ALERT_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)

type UkraineAlarmConfigEntry = ConfigEntry[UkraineAlarmDataUpdateCoordinator]


@dataclass(slots=True)
class AlertLevel:
    """Details of an air alert level that is active for a region."""

    reasons: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass(slots=True)
class RegionAlerts:
    """The alerts that are active for a region."""

    active: dict[str, bool]
    levels: dict[str, AlertLevel]


def _merge_level(level: AlertLevel, reported: dict[str, Any]) -> None:
    """Merge one reported level into the details collected for that level.

    A region can hold several air alerts at once and each of them can report
    the same level, so reasons are collected into a list and the oldest start
    time wins. An empty reason carries no information and is skipped.
    """
    reason = reported.get("reason")
    if reason and reason not in level.reasons:
        level.reasons.append(reason)

    created_at = dt_util.parse_datetime(reported.get("createdAt") or "")
    if created_at and (level.created_at is None or created_at < level.created_at):
        level.created_at = created_at


class UkraineAlarmDataUpdateCoordinator(DataUpdateCoordinator[RegionAlerts]):
    """Class to manage fetching Ukraine Alarm API."""

    config_entry: UkraineAlarmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UkraineAlarmConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize."""
        self.region_id = config_entry.data[CONF_REGION]
        self.uasiren = Client(session)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> RegionAlerts:
        """Update data via library."""
        try:
            res = await self.uasiren.get_alerts(self.region_id)
        except aiohttp.ClientError as error:
            raise UpdateFailed(f"Error fetching alerts from API: {error}") from error

        active = dict.fromkeys(ALERT_TYPES, False)
        levels = {key: AlertLevel() for key in AIR_ALERT_LEVELS.values()}
        for alert in res[0]["activeAlerts"]:
            active[alert["type"]] = True

            if alert["type"] != ALERT_TYPE_AIR:
                continue
            for reported in alert.get("activeAlertLevels") or []:
                key = AIR_ALERT_LEVELS.get(str(reported.get("alertLevel")).lower())
                if key is None:
                    continue
                active[key] = True
                _merge_level(levels[key], reported)

        return RegionAlerts(active, levels)
