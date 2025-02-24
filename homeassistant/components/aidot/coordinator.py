"""Coordinator for Aidot."""

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from aidot.client import AidotClient
from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_AES_KEY,
    CONF_ID,
    CONF_LOGIN_INFO,
    CONF_TYPE,
)
from aidot.discover import Discover
from aidot.exceptions import AidotAuthFailed, AidotUserOrPassIncorrect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

type AidotConfigEntry = ConfigEntry[AidotCoordinator]


class AidotCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching IOmeter data."""

    config_entry: AidotConfigEntry
    client: AidotClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AidotConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = AidotClient(
            session=async_get_clientsession(hass),
            token=config_entry.data[CONF_LOGIN_INFO],
        )
        self.client.set_token_fresh_cb(self.token_fresh_cb)
        self.identifier = config_entry.entry_id

    def filter_light_list(self):
        """Filter light."""
        return [
            device
            for device in self.data
            if device[CONF_TYPE] == Platform.LIGHT
            and CONF_AES_KEY in device
            and device[CONF_AES_KEY][0] is not None
        ]

    def token_fresh_cb(self):
        """Update token."""
        data = {**self.config_entry.data, CONF_LOGIN_INFO: self.client.login_info}

        @callback
        def async_update_entry() -> None:
            """Update config entry."""
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)

        self.hass.add_job(async_update_entry)

    async def async_auto_login(self):
        """Async auto login."""
        if self.client.login_info[CONF_ACCESS_TOKEN] is None:
            try:
                login_info = await self.client.async_post_login()
                if login_info is not None:
                    self.token_fresh_cb()
            except AidotUserOrPassIncorrect as error:
                raise AidotUserOrPassIncorrect from error

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data async."""
        try:
            device_list = await self.client.async_get_all_device()
        except AidotAuthFailed as error:
            self.token_fresh_cb()
            raise ConfigEntryAuthFailed from error
        return device_list

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Can be overwritten by integrations to load data or resources
        only once during the first refresh.
        """

        def discover(dev_id, event: Mapping[str, Any]):
            self.hass.bus.async_fire(dev_id, event)

        return await Discover().broadcast_message(
            discover, self.client.login_info[CONF_ID]
        )
