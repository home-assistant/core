"""Coordinator for Glances integration."""

from datetime import datetime, timedelta
import logging
from typing import Any

from glances_api import Glances, exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import parse_duration, utcnow

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GlancesConfigEntry = ConfigEntry[GlancesDataUpdateCoordinator]


class GlancesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get the latest data from Glances api."""

    config_entry: GlancesConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: GlancesConfigEntry, api: Glances
    ) -> None:
        """Initialize the Glances data."""
        self.hass = hass
        self.host: str = entry.data[CONF_HOST]
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest data from the Glances REST API."""
        try:
            data = await self.api.get_ha_sensor_data()
        except exceptions.GlancesApiAuthorizationError as err:
            raise ConfigEntryAuthFailed from err
        except exceptions.GlancesApiError as err:
            raise UpdateFailed from err
        # Update computed values
        uptime: datetime | None = None
        up_duration: timedelta | None = None
        if "uptime" in data and (up_duration := parse_duration(data["uptime"])):
            uptime = self.data["computed"]["uptime"] if self.data else None
            # Update uptime if previous value is None or previous uptime is bigger than
            # new uptime (i.e. server restarted)
            if uptime is None or self.data["computed"]["uptime_duration"] > up_duration:
                uptime = utcnow() - up_duration
        data["computed"] = {"uptime_duration": up_duration, "uptime": uptime}
        return data or {}
