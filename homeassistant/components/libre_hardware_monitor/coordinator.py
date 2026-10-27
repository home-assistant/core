"""Coordinator for LibreHardwareMonitor integration."""

from datetime import timedelta
import logging
from typing import override

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
    LibreHardwareMonitorUnauthorizedError,
)
from librehardwaremonitor_api.model import LibreHardwareMonitorData

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


type LibreHardwareMonitorConfigEntry = ConfigEntry[LibreHardwareMonitorCoordinator]


class LibreHardwareMonitorCoordinator(DataUpdateCoordinator[LibreHardwareMonitorData]):
    """Class to manage fetching LibreHardwareMonitor data."""

    config_entry: LibreHardwareMonitorConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._entry_id = config_entry.entry_id
        self._api = LibreHardwareMonitorClient(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            username=config_entry.data.get(CONF_USERNAME),
            password=config_entry.data.get(CONF_PASSWORD),
            session=async_create_clientsession(hass),
        )

    @override
    async def _async_update_data(self) -> LibreHardwareMonitorData:
        try:
            lhm_data = await self._api.get_data()
        except LibreHardwareMonitorConnectionError as err:
            raise UpdateFailed(
                "LibreHardwareMonitor connection failed, will retry", retry_after=25
            ) from err
        except LibreHardwareMonitorUnauthorizedError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except LibreHardwareMonitorNoDevicesError as err:
            raise UpdateFailed("No sensor data available, will retry") from err

        if lhm_data.is_deprecated_version:
            if self.config_entry.state is ConfigEntryState.LOADED:
                # if user downgrades while HA is running, reload integration to surface ConfigEntryError
                self.hass.config_entries.async_schedule_reload(self._entry_id)
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="deprecated_version",
            )

        return lhm_data

    @override
    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        # we don't expect the computer to be online 24/7 so
        # we don't want to log a connection loss as an error
        await super()._async_refresh(
            False, raise_on_auth_failed, scheduled, raise_on_entry_error
        )
