"""Data coordinator for the GPSD integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from gps3.agps3threaded import AGPS3mechanism

from homeassistant.const import (
    ATTR_ELEVATION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ATTR_CLIMB, ATTR_GPS_TIME, ATTR_SPEED

UPDATE_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)


class GpsdCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom coordinator for the GPSD integration."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the GPSD coordinator."""
        super().__init__(
            hass, _LOGGER, name=config[CONF_NAME], update_interval=UPDATE_INTERVAL
        )

        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

        self._agps_thread = AGPS3mechanism()
        self._agps_thread.stream_data(host=host, port=port)
        self._agps_thread.run_thread()

    def _get_value(self, value: str | None = None) -> Any:
        """Replace the GPSD response 'n/a' value with None."""
        return None if (value is None or value == "n/a") else value

    def _sync_update(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from GPSD."""
        return {
            ATTR_LATITUDE: self._get_value(self._agps_thread.data_stream.lat),
            ATTR_LONGITUDE: self._get_value(self._agps_thread.data_stream.lon),
            ATTR_ELEVATION: self._get_value(self._agps_thread.data_stream.alt),
            ATTR_GPS_TIME: self._get_value(self._agps_thread.data_stream.time),
            ATTR_SPEED: self._get_value(self._agps_thread.data_stream.speed),
            ATTR_CLIMB: self._get_value(self._agps_thread.data_stream.climb),
            ATTR_MODE: self._get_value(self._agps_thread.data_stream.mode),
        }

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from GPSD."""
        return await self.hass.async_add_executor_job(self._sync_update)
