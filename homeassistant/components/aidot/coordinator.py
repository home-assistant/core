"""Coordinator for Aidot."""

import logging
from typing import Any

from aidot.client import AidotClient
from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_AES_KEY,
    CONF_DEVICE_LIST,
    CONF_ID,
    CONF_LOGIN_INFO,
    CONF_TYPE,
)
from aidot.device_client import DeviceClient, DeviceStatusData
from aidot.exceptions import AidotAuthFailed, AidotNotLogin, AidotUserOrPassIncorrect

from homeassistant.components.sensor import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

type AidotConfigEntry = ConfigEntry[AidotDeviceManagerCoordinator]
_LOGGER = logging.getLogger(__name__)


class AidotDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceStatusData]):
    """Class to manage Aidot data."""

    device: dict[str, Any]
    ip_address: str
    device_client: DeviceClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AidotConfigEntry,
        device_client: DeviceClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=1),
        )
        self.device_client = device_client
        self.identifier = config_entry.entry_id

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Can be overwritten by integrations to load data or resources
        only once during the first refresh.
        """
        try:
            await self.device_client.async_login()
        except AidotUserOrPassIncorrect as error:
            raise ConfigEntryError from error

    async def _async_update_data(self) -> DeviceStatusData:
        """Update data async."""
        try:
            if self.device_client.connect_and_login is False:
                await self.device_client.async_login()
            status = await self.device_client.read_status()
        except AidotNotLogin:
            status = self.device_client.status
            status.online = False
        return status


class AidotDeviceManagerCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Aidot data."""

    config_entry: AidotConfigEntry
    client: AidotClient
    device_coordinators: dict[str, AidotDeviceUpdateCoordinator]

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
            update_interval=timedelta(hours=6),
        )
        self.client = AidotClient(
            session=async_get_clientsession(hass),
            token=config_entry.data[CONF_LOGIN_INFO],
        )
        self.client.start_discover()
        self.client.set_token_fresh_cb(self.token_fresh_cb)
        self.identifier = config_entry.entry_id
        self.device_coordinators = {}

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Can be overwritten by integrations to load data or resources
        only once during the first refresh.
        """
        try:
            await self.async_auto_login()
        except AidotUserOrPassIncorrect as error:
            raise ConfigEntryError from error

    async def _async_update_data(self) -> None:
        """Update data async."""
        try:
            data = await self.client.async_get_all_device()
        except AidotAuthFailed as error:
            self.token_fresh_cb()
            raise ConfigEntryError from error

        for device in data.get(CONF_DEVICE_LIST):
            if (
                device[CONF_TYPE] == Platform.LIGHT
                and CONF_AES_KEY in device
                and device[CONF_AES_KEY][0] is not None
            ):
                dev_id = device.get(CONF_ID)
                if dev_id not in self.device_coordinators:
                    device_client = self.client.get_device_client(device)
                    device_coordinator = AidotDeviceUpdateCoordinator(
                        self.hass, self.config_entry, device_client
                    )
                    await device_coordinator.async_config_entry_first_refresh()
                    self.device_coordinators[dev_id] = device_coordinator

    def cleanup(self) -> None:
        """Perform cleanup actions."""
        self.client.cleanup()

    def token_fresh_cb(self) -> None:
        """Update token."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={CONF_LOGIN_INFO: self.client.login_info.copy()}
        )

    async def async_auto_login(self) -> None:
        """Async auto login."""
        if self.client.login_info.get(CONF_ACCESS_TOKEN) is None:
            try:
                await self.client.async_post_login()
            except AidotUserOrPassIncorrect as error:
                raise AidotUserOrPassIncorrect from error
