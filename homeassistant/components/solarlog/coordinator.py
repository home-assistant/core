"""DataUpdateCoordinator for solarlog integration."""

from __future__ import annotations

from collections.abc import Callable
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
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import DOMAIN

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

        self.new_device_callbacks: list[Callable[[int], None]] = []
        self._devices_last_update: set[tuple[int, str]] = set()

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
            if logged_in := await self.renew_authentication():
                await self.solarlog.test_extended_data_available()
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

        if self.solarlog.extended_data:
            self._async_add_remove_devices(data)
            _LOGGER.debug("Add_remove_devices finished")

        return data

    def _async_add_remove_devices(self, data: SolarlogData) -> None:
        """Add new devices, remove non-existing devices."""
        if (
            current_devices := {
                (k, self.solarlog.device_name(k)) for k in data.inverter_data
            }
        ) == self._devices_last_update:
            return

        # remove old devices
        if removed_devices := self._devices_last_update - current_devices:
            _LOGGER.debug("Removed device(s): %s", ", ".join(map(str, removed_devices)))
            device_registry = dr.async_get(self.hass)

            for removed_device in removed_devices:
                device_name = ""
                for did, dn in self._devices_last_update:
                    if did == removed_device[0]:
                        device_name = dn
                        break
                if device := device_registry.async_get_device(
                    identifiers={
                        (
                            DOMAIN,
                            f"{self.unique_id}_{slugify(device_name)}",
                        )
                    }
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.unique_id,
                    )
                    _LOGGER.debug("Device removed from device registry: %s", device.id)

        # add new devices
        if new_devices := current_devices - self._devices_last_update:
            _LOGGER.debug("New device(s) found: %s", ", ".join(map(str, new_devices)))
            for device_id in new_devices:
                for callback in self.new_device_callbacks:
                    callback(device_id[0])

        self._devices_last_update = current_devices

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
