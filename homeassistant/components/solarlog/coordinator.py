"""DataUpdateCoordinator for solarlog integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, urlparse

from solarlog_cli.solarlog_connector import SolarLogConnector
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogUpdateError,
)
from solarlog_cli.solarlog_models import SolarlogData

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import SolarlogConfigEntry


class SolarLogCoordinator(DataUpdateCoordinator[SolarlogData]):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: SolarlogConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name="SolarLog", update_interval=timedelta(seconds=60)
        )

        host_entry = entry.data[CONF_HOST]
        password = entry.data.get("password", "")

        url = urlparse(host_entry, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        self.unique_id = entry.entry_id
        self.name = entry.title
        self.host = url.geturl()

        self.solarlog = SolarLogConnector(
            self.host,
            tz=hass.config.time_zone,
            password=password,
        )

    async def _async_setup(self) -> None:
        """Do initialization logic."""
        _LOGGER.debug("Start async_setup")
        logged_in = False
        if self.solarlog.password != "":
            logged_in = await self.renew_authentication()
        if logged_in or await self.solarlog.test_extended_data_available():
            device_list = await self.solarlog.update_device_list()
            self.solarlog.set_enabled_devices({key: True for key in device_list})

    async def _async_update_data(self) -> SolarlogData:
        """Update the data from the SolarLog device."""
        _LOGGER.debug("Start data update")

        try:
            data = await self.solarlog.update_data()
            if self.solarlog.extended_data:
                await self.solarlog.update_device_list()
                data.inverter_data = await self.solarlog.update_inverter_data()
        except SolarLogConnectionError as ex:
            raise ConfigEntryNotReady(ex) from ex
        except SolarLogAuthenticationError as ex:
            if await self.renew_authentication():
                # login was successful, update availability of extended data, retry data update
                await self.solarlog.test_extended_data_available()
                raise ConfigEntryNotReady from ex
            raise ConfigEntryAuthFailed from ex
        except SolarLogUpdateError as ex:
            raise UpdateFailed(ex) from ex

        _LOGGER.debug("Data successfully updated")

        return data

    async def renew_authentication(self) -> bool:
        """Renew access token for SolarLog API."""
        logged_in = False
        try:
            logged_in = await self.solarlog.login()
        except SolarLogAuthenticationError as ex:
            raise ConfigEntryAuthFailed from ex
        except (SolarLogConnectionError, SolarLogUpdateError) as ex:
            raise ConfigEntryNotReady from ex

        _LOGGER.debug("Credentials successfully updated? %s", logged_in)

        return logged_in
