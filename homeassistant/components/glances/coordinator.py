"""Coordinator for Glances integration."""

from datetime import datetime
import logging
from typing import Any

from glances_api import Glances, exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import parse_duration, utcnow

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_UPTIME_VARIATION

_LOGGER = logging.getLogger(__name__)


class GlancesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get the latest data from Glances api."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: Glances) -> None:
        """Initialize the Glances data."""
        self.hass = hass
        self.config_entry = entry
        self.host: str = entry.data[CONF_HOST]
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
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
        if data:
            uptime = self._convert_uptime(data.get("uptime"))
            data.update({"computed": {"uptime": uptime}})
        return data or {}

    def _convert_uptime(self, uptime_str: str | None) -> datetime | None:
        """Convert Glances uptime (duration) to datetime."""
        uptime = None
        if uptime_str:
            up_duration = parse_duration(uptime_str)
            if up_duration:
                uptime = utcnow() - up_duration
        if uptime and self.data:
            previous_uptime = self.data["computed"]["uptime"]
            if (
                isinstance(previous_uptime, datetime)
                and uptime - previous_uptime < MIN_UPTIME_VARIATION
            ):
                uptime = previous_uptime
        return uptime
