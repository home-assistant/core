"""Coordinator for the Uptime Kuma integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyuptimekuma import (
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
    UptimeKumaMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
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
        self, hass: HomeAssistant, config_entry: UptimeKumaConfigEntry, api: UptimeKuma
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_setup(self) -> None:
        """Set up coordinator."""

        try:
            await self.api.async_get_monitors()
        except UptimeKumaAuthenticationException as e:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed_exception",
            ) from e
        except UptimeKumaException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="request_failed_exception",
            ) from e

    async def _async_update_data(self) -> dict[str, UptimeKumaMonitor]:
        """Fetch the latest data from Uptime Kuma."""

        try:
            return {
                monitor.monitor_name: monitor
                for monitor in (await self.api.async_get_monitors()).data
            }
        except UptimeKumaException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_failed_exception",
            ) from e
