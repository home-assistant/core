"""Coordinator for Aidot."""

from collections.abc import Callable
import logging
from typing import Any

from aidot.client import AidotClient
from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_AES_KEY,
    CONF_DEVICE_LIST,
    CONF_LOGIN_INFO,
    CONF_TYPE,
)
from aidot.discover import Discover
from aidot.exceptions import AidotAuthFailed, AidotOSError, AidotUserOrPassIncorrect

from homeassistant.components.sensor import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type AidotConfigEntry = ConfigEntry[AidotCoordinator]
_LOGGER = logging.getLogger(__name__)


class AidotDeviceUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Aidot data."""

    config_entry: ConfigEntry
    client: AidotClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=6),
        )
        self.client = AidotClient(
            session=async_get_clientsession(hass),
            token=config_entry.data[CONF_LOGIN_INFO],
        )
        self.client.set_token_fresh_cb(self.token_fresh_cb)
        self.identifier = config_entry.entry_id

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Can be overwritten by integrations to load data or resources
        only once during the first refresh.
        """
        try:
            await self.async_auto_login()
        except AidotUserOrPassIncorrect as error:
            raise ConfigEntryError from error

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data async."""
        try:
            device_list = await self.client.async_get_all_device()
        except AidotAuthFailed as error:
            self.token_fresh_cb()
            raise ConfigEntryError from error
        return device_list

    def filter_light_list(self) -> list[dict[str, Any]]:
        """Filter light."""
        return [
            device
            for device in self.data[CONF_DEVICE_LIST]
            if device[CONF_TYPE] == Platform.LIGHT
            and CONF_AES_KEY in device
            and device[CONF_AES_KEY][0] is not None
        ]

    def token_fresh_cb(self) -> None:
        """Update token."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={CONF_LOGIN_INFO: self.client.login_info.copy()}
        )

    async def async_auto_login(self) -> None:
        """Async auto login."""
        if self.client.login_info.get(CONF_ACCESS_TOKEN) is None:
            try:
                login_info = await self.client.async_post_login()
                if login_info is not None:
                    self.token_fresh_cb()
            except AidotUserOrPassIncorrect as error:
                raise AidotUserOrPassIncorrect from error


class AidotDeviceDiscoverCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Class to manage discover device ip."""

    config_entry: ConfigEntry
    discover: Discover

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.identifier = config_entry.entry_id
        self.discover = Discover(config_entry.data[CONF_LOGIN_INFO])

    async def _async_update_data(self) -> dict[str, str]:
        """Update data async."""
        try:
            data = await self.discover.fetch_devices_info()
        except AidotOSError as error:
            raise UpdateFailed(f"Error Found Device with Aidot: {error}") from error
        return data

    @callback
    def async_add_listener(
        self, update_callback: Callable, context: Any = None
    ) -> Callable:
        """Wrap standard function to prune cached callback database and add cleanup."""
        release = super().async_add_listener(update_callback, context)

        @callback
        def release_update():
            release()
            self._cleanup(context)

        return release_update

    def _cleanup(self, context: Any):
        """Perform cleanup actions when a listener is removed."""
        self.discover.close()


class AidotCoordinator:
    """Class to manage Aidot data."""

    discover_coordinator: AidotDeviceDiscoverCoordinator
    update_coordinator: AidotDeviceUpdateCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AidotConfigEntry,
    ) -> None:
        """Initialize coordinator."""

        self.discover_coordinator = AidotDeviceDiscoverCoordinator(hass, config_entry)
        self.update_coordinator = AidotDeviceUpdateCoordinator(hass, config_entry)

    async def async_config_entry_first_refresh(self) -> None:
        """Discover device ip and fetch device list."""
        await self.discover_coordinator.async_config_entry_first_refresh()
        await self.update_coordinator.async_config_entry_first_refresh()

    def filter_light_list(self) -> list[dict[str, Any]]:
        """Filter light."""
        return self.update_coordinator.filter_light_list()
