"""Coordinator for the Uptime Kuma integration."""

from datetime import timedelta
import logging
from typing import override

from pythonkuma import (
    UpdateException,
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
    UptimeKumaMonitor,
    UptimeKumaParseException,
)
from pythonkuma.update import LatestRelease, UpdateChecker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
SCAN_INTERVAL_UPDATES = timedelta(hours=3)

type UptimeKumaConfigEntry = ConfigEntry[UptimeKumaDataUpdateCoordinator]


class UptimeKumaDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str | int, UptimeKumaMonitor]]
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
            update_interval=SCAN_INTERVAL,
        )
        session = async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL])
        self.api = UptimeKuma(
            session, config_entry.data[CONF_URL], config_entry.data[CONF_API_KEY]
        )

    @override
    async def _async_update_data(self) -> dict[str | int, UptimeKumaMonitor]:
        """Fetch the latest data from Uptime Kuma."""

        try:
            metrics = await self.api.metrics()
        except UptimeKumaAuthenticationException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed_exception",
            ) from e
        except UptimeKumaParseException as e:
            _LOGGER.debug("Full exception", exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="parsing_failed_exception",
            ) from e
        except UptimeKumaException as e:
            _LOGGER.debug("Full exception", exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_failed_exception",
            ) from e
        else:
            if int(self.api.version.major) < 2:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_version",
                )

            return metrics


class UptimeKumaSoftwareUpdateCoordinator(DataUpdateCoordinator[LatestRelease]):
    """Uptime Kuma coordinator for retrieving update information."""

    def __init__(self, hass: HomeAssistant, update_checker: UpdateChecker) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_UPDATES,
        )
        self.update_checker = update_checker

    @override
    async def _async_update_data(self) -> LatestRelease:
        """Fetch data."""
        try:
            return await self.update_checker.latest_release()
        except UpdateException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_check_failed",
            ) from e
