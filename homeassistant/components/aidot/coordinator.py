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
from aidot.device_client import DeviceClient, DeviceInformation, DeviceStatusData
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
        # self.hass.loop.create_task(device_client.ping_task())
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
            status = await self.device_client.read_status()
        except AidotNotLogin:
            await self.device_client.async_login()
            return DeviceStatusData()
        return status

    @property
    def device_info(self) -> DeviceInformation:
        """Device information."""
        return self.device_client.info


class AidotDeviceManagerCoordinator(
    DataUpdateCoordinator[dict[str, AidotDeviceUpdateCoordinator]]
):
    """Class to manage fetching Aidot data."""

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
            update_interval=timedelta(hours=6),
        )
        self.client = AidotClient(
            session=async_get_clientsession(hass),
            token=config_entry.data[CONF_LOGIN_INFO],
        )
        self.client.start_discover()
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
            data = await self.client.async_get_all_device()
        except AidotAuthFailed as error:
            self.token_fresh_cb()
            raise ConfigEntryError from error

        current_coordinators: dict[str, AidotDeviceUpdateCoordinator] = self.data
        if current_coordinators is None:
            current_coordinators = {}
        final_coordinators: dict[str, AidotDeviceUpdateCoordinator] = {}
        for device in data.get(CONF_DEVICE_LIST):
            if (
                device[CONF_TYPE] == Platform.LIGHT
                and CONF_AES_KEY in device
                and device[CONF_AES_KEY][0] is not None
            ):
                dev_id = device.get(CONF_ID)
                update_coordinator = current_coordinators.get(dev_id)
                device_client = self.client.get_device_client(device)
                if update_coordinator is None:
                    update_coordinator = AidotDeviceUpdateCoordinator(
                        self.hass, self.config_entry, device_client
                    )
                    await update_coordinator.async_config_entry_first_refresh()
                final_coordinators[dev_id] = update_coordinator
        return final_coordinators

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
