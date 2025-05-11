"""Data coordinator for the qnap integration."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import timedelta
import logging
from typing import Any

from qnapstats import QNAPStats
import urllib3

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

UPDATE_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)


@contextmanager
def suppress_insecure_request_warning():
    """Context manager to suppress InsecureRequestWarning.

    Was added in here to solve the following issue, not being solved upstream.
    https://github.com/colinodell/python-qnapstats/issues/96
    """
    with urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning):
        try:
            yield
        finally:
            pass


class QnapCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Custom coordinator for the qnap integration."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the qnap coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        protocol = "https" if config_entry.data[CONF_SSL] else "http"
        self._verify_ssl = config_entry.data.get(CONF_VERIFY_SSL)

        self._api = QNAPStats(
            f"{protocol}://{config_entry.data.get(CONF_HOST)}",
            config_entry.data.get(CONF_PORT),
            config_entry.data.get(CONF_USERNAME),
            config_entry.data.get(CONF_PASSWORD),
            verify_ssl=self._verify_ssl,
            timeout=config_entry.data.get(CONF_TIMEOUT),
        )

    def _sync_update(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from the Qnap API."""
        with (
            suppress_insecure_request_warning()
            if not self._verify_ssl
            else nullcontext()
        ):
            return {
                "system_stats": self._api.get_system_stats(),
                "system_health": self._api.get_system_health(),
                "smart_drive_health": self._api.get_smart_disk_health(),
                "volumes": self._api.get_volumes(),
                "bandwidth": self._api.get_bandwidth(),
            }

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from the Qnap API."""
        return await self.hass.async_add_executor_job(self._sync_update)
