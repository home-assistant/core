"""Coordinator for the LibreNMS integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiolibrenms import Librenms
from aiolibrenms.const import CONNECT_ERRORS
from aiolibrenms.devices.models import LibrenmsDeviceInfo
from aiolibrenms.exceptions import LibrenmsUnauthenticatedError
from aiolibrenms.system.models import LibrenmsSystemInfo
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LibrenmsData:
    """Data class for storing data from the API."""

    system: LibrenmsSystemInfo
    devices: list[LibrenmsDeviceInfo]


type LibrenmsConfigEntry = ConfigEntry[LibrenmsDataUpdateCoordinator]


class LibrenmsDataUpdateCoordinator(DataUpdateCoordinator[LibrenmsData]):
    """Class to manage fetching LibreNMS data."""

    config_entry: LibrenmsConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: LibrenmsConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self.api = Librenms(
            async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL]),
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_SSL],
        )
        self.configuration_url = str(
            URL.build(
                scheme="https" if config_entry.data[CONF_SSL] else "http",
                host=config_entry.data[CONF_HOST],
                port=config_entry.data[CONF_PORT],
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    @override
    async def _async_setup(self) -> None:
        """Handle setup of the coordinator."""
        try:
            await self.api.system.async_get_system_info()
        except LibrenmsUnauthenticatedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    @override
    async def _async_update_data(self) -> LibrenmsData:
        """Update data via internal method."""
        try:
            system = await self.api.system.async_get_system_info()
            devices = await self.api.devices.async_get_devices()
        except LibrenmsUnauthenticatedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return LibrenmsData(system, devices)
