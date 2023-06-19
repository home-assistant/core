"""Data coordinator for the qnap integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from qnapstats import QNAPStats

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
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

UPDATE_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)


class QnapCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Custom coordinator for the qnap integration."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the qnap coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

        protocol = "https" if config[CONF_SSL] else "http"
        self._api = QNAPStats(
            f"{protocol}://{config.get(CONF_HOST)}",
            config.get(CONF_PORT),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            verify_ssl=config.get(CONF_VERIFY_SSL),
            timeout=config.get(CONF_TIMEOUT),
        )

    def _sync_update(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from the Qnap API."""
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
