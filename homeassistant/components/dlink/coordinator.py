"""Coordinator for Dlink."""

from datetime import datetime, timedelta
import logging
import urllib

from pyW215.pyW215 import SmartPlug

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DlinkCoordinator(DataUpdateCoordinator[SmartPlug]):
    """Class to manage fetching Dlink data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, smartplug: SmartPlug) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.smartplug = smartplug
        self.available = False
        self._n_tried = 0
        self._last_tried: datetime | None = None

    def _update_data(self) -> SmartPlug:
        """Fetch data from Dlink API via sync functions."""

        if self._last_tried is not None:
            last_try_s = (dt_util.now() - self._last_tried).total_seconds() / 60
            retry_seconds = min(self._n_tried * 2, 10) - last_try_s
            if self._n_tried > 0 and retry_seconds > 0:
                _LOGGER.warning("Waiting %s s to retry", retry_seconds)
                return None

        _state = "unknown"

        try:
            self._last_tried = dt_util.now()
            _state = self.smartplug.state
        except urllib.error.HTTPError:
            _LOGGER.error("D-Link connection problem")
        if _state == "unknown":
            self._n_tried += 1
            self.available = False
            _LOGGER.warning("Failed to connect to D-Link switch")
            return None

        self.available = True

        self._n_tried = 0
        return self.smartplug

    async def _async_update_data(self) -> SmartPlug:
        """Fetch data from Dlink API."""
        return await self.hass.async_add_executor_job(self._update_data)
