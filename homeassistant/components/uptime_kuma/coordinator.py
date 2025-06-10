"""Coordinator for the Uptime Kuma integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pythonkuma import (
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
    UptimeKumaMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type UptimeKumaConfigEntry = ConfigEntry[UptimeKumaDataUpdateCoordinator]


class UptimeKumaDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, UptimeKumaMonitor]]
):
    """Update coordinator for Uptime Kuma."""

    config_entry: UptimeKumaConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: UptimeKumaConfigEntry
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        session = async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL])
        self.api = UptimeKuma(
            session, config_entry.data[CONF_URL], "", config_entry.data[CONF_API_KEY]
        )

    async def _async_update_data(self) -> dict[str, UptimeKumaMonitor]:
        """Fetch the latest data from Uptime Kuma."""

        try:
            data = (await self.api.async_get_monitors()).data or []
            return {monitor.monitor_name: monitor for monitor in data}
        except UptimeKumaAuthenticationException as e:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="auth_failed_exception",
            ) from e
        except UptimeKumaException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_failed_exception",
            ) from e
